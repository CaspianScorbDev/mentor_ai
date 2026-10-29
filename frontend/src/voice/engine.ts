const ROOT = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";

function apiRoot(): string {
  return ROOT.replace(/\/$/, "");
}

function socketBase(): string {
  const root = apiRoot();
  if (root) return root.replace(/^http/, "ws");
  // Same-origin build (empty VITE_API_BASE): WebSocket needs an absolute URL.
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${window.location.host}`;
}

export function voiceSocketUrl(): string {
  return `${socketBase()}/api/v1/voice/tts`;
}

export interface VoiceInfoDto {
  name: string;
  title: string;
  kind: "builtin" | "cloned";
  language: string | null;
}

export interface VoiceStatusDto {
  backend: string;
  ready: boolean;
  model: string;
  sample_rate: number;
  default_voice: string | null;
  detail: string | null;
  voices: VoiceInfoDto[];
}

/** Microphone capture with an analyser used to drive the orb while listening. */
export class MicCapture {
  private ctx: AudioContext;
  private stream: MediaStream;
  private source: MediaStreamAudioSourceNode;
  private analyser: AnalyserNode;
  private data: Uint8Array<ArrayBuffer>;
  private muted = false;

  private constructor(
    ctx: AudioContext,
    stream: MediaStream,
    source: MediaStreamAudioSourceNode,
    analyser: AnalyserNode,
  ) {
    this.ctx = ctx;
    this.stream = stream;
    this.source = source;
    this.analyser = analyser;
    this.data = new Uint8Array(new ArrayBuffer(analyser.fftSize));
  }

  static async open(): Promise<MicCapture> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    await ctx.resume();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);
    return new MicCapture(ctx, stream, source, analyser);
  }

  /** Normalised RMS level in the 0..1 range. */
  level(): number {
    if (this.muted) return 0;
    this.analyser.getByteTimeDomainData(this.data);
    let sum = 0;
    for (let i = 0; i < this.data.length; i += 1) {
      const v = (this.data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.sqrt(sum / this.data.length);
    return Math.min(1, rms * 3.2);
  }

  /**
   * Gate the mic input. While muted, `level()` reports silence so the orb stops
   * reacting to speaker output, and callers can pause recognition to avoid the
   * assistant transcribing its own voice (acoustic feedback).
   */
  setMuted(muted: boolean): void {
    this.muted = muted;
    this.stream.getAudioTracks().forEach((track) => {
      track.enabled = !muted;
    });
  }

  close(): void {
    try {
      this.source.disconnect();
      this.stream.getTracks().forEach((track) => track.stop());
      void this.ctx.close();
    } catch {
      /* already closed */
    }
  }
}

/** Plays a stream of 16-bit PCM chunks with gapless scheduling. */
export class PcmStreamPlayer {
  private ctx: AudioContext;
  private gain: GainNode;
  private analyser: AnalyserNode;
  private data: Uint8Array<ArrayBuffer>;
  private nextTime = 0;
  private active = new Set<AudioBufferSourceNode>();

  constructor() {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.gain = this.ctx.createGain();
    // TTS PCM peaks near full scale (±32768). Keep some headroom so speech
    // never clips and the speakers aren't driven hard enough to feed the mic.
    this.gain.gain.value = 0.7;
    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 512;
    this.gain.connect(this.analyser);
    this.analyser.connect(this.ctx.destination);
    this.data = new Uint8Array(new ArrayBuffer(this.analyser.fftSize));
  }

  get busy(): boolean {
    return this.active.size > 0;
  }

  push(int16: Int16Array, sampleRate: number): void {
    if (int16.length === 0) return;
    if (this.ctx.state === "suspended") void this.ctx.resume();
    const buffer = this.ctx.createBuffer(1, int16.length, sampleRate);
    const channel = buffer.getChannelData(0);
    for (let i = 0; i < int16.length; i += 1) channel[i] = int16[i] / 32768;

    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gain);
    const start = Math.max(this.ctx.currentTime + 0.02, this.nextTime);
    source.start(start);
    this.nextTime = start + buffer.duration;
    this.active.add(source);
    source.onended = () => this.active.delete(source);
  }

  level(): number {
    this.analyser.getByteTimeDomainData(this.data);
    let sum = 0;
    for (let i = 0; i < this.data.length; i += 1) {
      const v = (this.data[i] - 128) / 128;
      sum += v * v;
    }
    return Math.min(1, Math.sqrt(sum / this.data.length) * 3.2);
  }

  cancel(): void {
    for (const source of this.active) {
      try {
        source.stop();
      } catch {
        /* already stopped */
      }
    }
    this.active.clear();
    this.nextTime = 0;
  }

  close(): void {
    this.cancel();
    void this.ctx.close();
  }
}

export interface TtsSocketHandlers {
  onReady?: (info: { backend: string; sample_rate: number }) => void;
  onAudio: (pcm: Int16Array) => void;
  onDone: () => void;
  onError: (detail: string) => void;
}

interface ServerMessage {
  type: string;
  data?: string;
  detail?: string;
  backend?: string;
  sample_rate?: number;
}

/** Persistent PCM channel to the backend TTS streamer. */
export class TtsSocket {
  private ws: WebSocket | null = null;
  private handlers: TtsSocketHandlers;
  private queue: string[] = [];
  private voice: string | null = null;

  constructor(handlers: TtsSocketHandlers) {
    this.handlers = handlers;
  }

  connect(voice: string | null): void {
    this.voice = voice;
    const ws = new WebSocket(voiceSocketUrl());
    this.ws = ws;
    ws.onopen = () => {
      if (this.voice) ws.send(JSON.stringify({ type: "config", voice: this.voice }));
      for (const text of this.queue) ws.send(JSON.stringify({ type: "speak", text }));
      this.queue = [];
    };
    ws.onmessage = (event) => this.dispatch(event.data as string);
    ws.onerror = () => this.handlers.onError("Голосовое соединение недоступно");
    ws.onclose = () => {
      this.ws = null;
    };
  }

  private dispatch(raw: string): void {
    let message: ServerMessage;
    try {
      message = JSON.parse(raw) as ServerMessage;
    } catch {
      return;
    }
    if (message.type === "ready") {
      this.handlers.onReady?.({
        backend: message.backend ?? "local",
        sample_rate: message.sample_rate ?? 24000,
      });
    } else if (message.type === "audio" && message.data) {
      this.handlers.onAudio(decodePcm(message.data));
    } else if (message.type === "done") {
      this.handlers.onDone();
    } else if (message.type === "error") {
      this.handlers.onError(message.detail ?? "Ошибка синтеза");
    }
  }

  setVoice(voice: string | null): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "config", voice }));
    }
  }

  speak(text: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "speak", text }));
    } else {
      this.queue.push(text);
    }
  }

  cancel(): void {
    this.queue = [];
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "cancel" }));
    }
  }

  close(): void {
    this.queue = [];
    this.ws?.close();
    this.ws = null;
  }
}

function decodePcm(base64: string): Int16Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const view = new DataView(bytes.buffer);
  const count = Math.floor(bytes.byteLength / 2);
  const out = new Int16Array(count);
  for (let i = 0; i < count; i += 1) out[i] = view.getInt16(i * 2, true);
  return out;
}
