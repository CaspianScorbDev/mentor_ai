import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Loader2,
  Mic,
  Plus,
  Search,
  Square,
  X,
} from "lucide-react";
import { api, type SourceItem, type StreamOptions, type VoiceStatusDto } from "../api";
import { MicCapture, PcmStreamPlayer, TtsSocket } from "../voice/engine";
import { getSpeechRecognition, type SpeechRecognitionLike } from "../speech";
import { VoiceOrb, type VoicePhase } from "./VoiceOrb";

export interface AskMentorHandlers {
  onDelta: (chunk: string) => void;
  onDone: (message?: unknown) => void;
  onError: (detail: string) => void;
  onThinking?: (chunk: string) => void;
  onSources?: (items: SourceItem[]) => void;
  onStatus?: (detail: string) => void;
}

export type AskMentor = (
  text: string,
  handlers: AskMentorHandlers,
  options?: StreamOptions,
) => void;

interface VoiceOverlayProps {
  open: boolean;
  onClose: () => void;
  askMentor: AskMentor;
}

const PHASE_LABEL: Record<VoicePhase, string> = {
  idle: "Готов слушать",
  listening: "Слушаю вас…",
  thinking: "Думаю…",
  speaking: "Отвечаю…",
};

function splitSentences(
  text: string,
  from: number,
  flushAll: boolean,
): { parts: string[]; consumed: number } {
  const slice = text.slice(from);
  const parts: string[] = [];
  let last = 0;
  const re = /[^.!?…\n]+[.!?…]+["»)\]]?\s*|\n+/g;
  let match: RegExpExecArray | null;
  while ((match = re.exec(slice)) !== null) {
    const part = match[0].trim();
    if (part) parts.push(part);
    last = re.lastIndex;
  }
  if (flushAll) {
    const rest = slice.slice(last).trim();
    if (rest) {
      parts.push(rest);
      last = slice.length;
    }
  }
  return { parts, consumed: from + last };
}

function cleanForSpeech(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_#>]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const VOICE_TAGS =
  /\[(?:angry|contemplative|excited|joyful|mundane|nervous|sad|stern|surprised|tender)\]|<(?:gasp|giggle|growl|gulp|laugh|scoff|sigh|sob|pause|um)>/gi;

function stripTags(text: string): string {
  return text.replace(VOICE_TAGS, "").replace(/\s{2,}/g, " ");
}

function isRussian(item: { language: string | null; name: string; title: string }): boolean {
  if ((item.language ?? "").toLowerCase().startsWith("ru")) return true;
  return /russian|русск/i.test(`${item.name} ${item.title}`);
}

const SAVED_VOICE_KEY = "aida-voice";

function pickDefaultVoice(data: VoiceStatusDto): string {
  const saved = localStorage.getItem(SAVED_VOICE_KEY);
  if (saved && data.voices.some((item) => item.name === saved)) return saved;
  if (data.default_voice) return data.default_voice;
  const preferred = data.voices.find(isRussian);
  return (preferred ?? data.voices[0])?.name ?? "";
}

export function VoiceOverlay({ open, onClose, askMentor }: VoiceOverlayProps) {
  const [phase, setPhaseState] = useState<VoicePhase>("idle");
  const [heard, setHeard] = useState("");
  const [reply, setReply] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<VoiceStatusDto | null>(null);
  const [voice, setVoice] = useState<string>("");
  const [typed, setTyped] = useState("");
  const [cloning, setCloning] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const supported = useMemo(() => getSpeechRecognition() !== null, []);
  const orderedVoices = useMemo(() => {
    if (!status) return [];
    const seen = new Set<string>();
    const unique = status.voices.filter((item) => {
      if (seen.has(item.name)) return false;
      seen.add(item.name);
      return true;
    });
    return unique.sort((a, b) => Number(isRussian(b)) - Number(isRussian(a)));
  }, [status]);
  const filteredVoices = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return orderedVoices;
    return orderedVoices.filter((item) =>
      `${item.title} ${item.name}`.toLowerCase().includes(q),
    );
  }, [orderedVoices, query]);
  const currentVoiceTitle = useMemo(() => {
    if (!status) return "Загрузка голосов…";
    const found = orderedVoices.find((item) => item.name === voice);
    return found?.title ?? (voice || "Выбрать голос");
  }, [orderedVoices, voice, status]);

  const phaseRef = useRef<VoicePhase>("idle");
  const openRef = useRef(false);
  const levelRef = useRef(0);
  const sampleRateRef = useRef(24000);
  const voiceRef = useRef("");
  const micRef = useRef<MicCapture | null>(null);
  const playerRef = useRef<PcmStreamPlayer | null>(null);
  const ttsRef = useRef<TtsSocket | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const restartRef = useRef<number | null>(null);
  const finalBufRef = useRef("");
  const fullReplyRef = useRef("");
  const emittedRef = useRef(0);
  const pendingRef = useRef(0);
  const streamDoneRef = useRef(false);

  const setPhase = useCallback((next: VoicePhase) => {
    phaseRef.current = next;
    setPhaseState(next);
  }, []);

  useEffect(() => {
    if (!open) return;
    openRef.current = true;
    let cancelled = false;
    let raf = 0;

    void api
      .getVoiceStatus()
      .then((data) => {
        if (cancelled) return;
        setStatus(data);
        const initial = pickDefaultVoice(data);
        setVoice(initial);
        voiceRef.current = initial;
        ttsRef.current?.setVoice(initial);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    const player = new PcmStreamPlayer();
    playerRef.current = player;

    const tts = new TtsSocket({
      onReady: (info) => {
        sampleRateRef.current = info.sample_rate;
      },
      onAudio: (pcm) => {
        player.push(pcm, sampleRateRef.current);
        if (phaseRef.current !== "speaking") setPhase("speaking");
      },
      onDone: () => {
        pendingRef.current = Math.max(0, pendingRef.current - 1);
        if (pendingRef.current === 0 && streamDoneRef.current) {
          setPhase(openRef.current ? "listening" : "idle");
        }
      },
      onError: (detail) => {
        pendingRef.current = 0;
        setError(detail);
        setPhase(openRef.current ? "listening" : "idle");
      },
    });
    ttsRef.current = tts;
    tts.connect(voiceRef.current || null);

    void MicCapture.open()
      .then((mic) => {
        if (cancelled) {
          mic.close();
          return;
        }
        micRef.current = mic;
        const loop = () => {
          levelRef.current = mic.level();
          raf = requestAnimationFrame(loop);
        };
        loop();
      })
      .catch(() => {
        if (!cancelled) setError("Нет доступа к микрофону");
      });

    const Ctor = getSpeechRecognition();
    if (!Ctor) {
      return () => {
        cancelled = true;
        openRef.current = false;
        cancelAnimationFrame(raf);
        micRef.current?.close();
        micRef.current = null;
        player.close();
        playerRef.current = null;
        tts.close();
        ttsRef.current = null;
      };
    }

    const emitReadySentences = (final: boolean) => {
      const { parts, consumed } = splitSentences(fullReplyRef.current, emittedRef.current, final);
      emittedRef.current = consumed;
      for (const part of parts) {
        const spoken = cleanForSpeech(part);
        if (!spoken) continue;
        pendingRef.current += 1;
        ttsRef.current?.speak(spoken);
      }
    };

    const handleUtterance = (text: string) => {
      if (!text.trim()) return;
      if (phaseRef.current === "speaking" || phaseRef.current === "thinking") {
        ttsRef.current?.cancel();
        playerRef.current?.cancel();
      }
      pendingRef.current = 0;
      streamDoneRef.current = false;
      fullReplyRef.current = "";
      emittedRef.current = 0;
      setReply("");
      setHeard(text);
      setPhase("thinking");
      askMentor(
        text,
        {
          onDelta: (chunk) => {
            fullReplyRef.current += chunk;
            setReply(stripTags(fullReplyRef.current));
            emitReadySentences(false);
          },
          onDone: () => {
            streamDoneRef.current = true;
            emitReadySentences(true);
            if (pendingRef.current === 0) setPhase(openRef.current ? "listening" : "idle");
          },
          onError: (detail) => {
            setError(detail);
            setPhase(openRef.current ? "listening" : "idle");
          },
        },
        { voice: true },
      );
    };

    const rec = new Ctor();
    rec.lang = "ru-RU";
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) finalBufRef.current += ` ${text}`;
        else interim += text;
      }
      setHeard(`${finalBufRef.current} ${interim}`.trim());
      const final = finalBufRef.current.trim();
      if (final) {
        finalBufRef.current = "";
        handleUtterance(final);
      }
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setError("Разрешите доступ к микрофону в браузере");
      }
    };
    rec.onend = () => {
      if (!openRef.current || phaseRef.current === "speaking") return;
      restartRef.current = window.setTimeout(() => {
        if (!openRef.current || phaseRef.current === "speaking") return;
        try {
          rec.start();
        } catch {
          /* already started */
        }
      }, 300);
    };
    recRef.current = rec;
    try {
      rec.start();
    } catch {
      /* start may throw if already running */
    }

    return () => {
      cancelled = true;
      openRef.current = false;
      if (restartRef.current !== null) window.clearTimeout(restartRef.current);
      restartRef.current = null;
      try {
        rec.abort();
      } catch {
        /* ignore */
      }
      recRef.current = null;
      cancelAnimationFrame(raf);
      micRef.current?.close();
      micRef.current = null;
      player.close();
      playerRef.current = null;
      tts.close();
      ttsRef.current = null;
    };
  }, [open, askMentor, setPhase]);

  useEffect(() => {
    if (!open) return;
    const speaking = phase === "speaking";
    micRef.current?.setMuted(speaking);
    const rec = recRef.current;
    if (!rec) return;
    if (speaking) {
      try {
        rec.abort();
      } catch {
        /* already stopped */
      }
    } else {
      try {
        rec.start();
      } catch {
        /* already started */
      }
    }
  }, [phase, open]);

  const applyVoice = useCallback((name: string) => {
    setVoice(name);
    voiceRef.current = name;
    ttsRef.current?.setVoice(name);
    try {
      localStorage.setItem(SAVED_VOICE_KEY, name);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const cloneFromFile = useCallback(
    async (file: File | null | undefined) => {
      if (!file) return;
      const suggested = file.name.replace(/\.[^.]+$/, "");
      const name = window.prompt("Название нового голоса:", suggested);
      if (!name || !name.trim()) return;
      setCloning(true);
      setError(null);
      try {
        const info = await api.cloneVoice(file, name.trim());
        const data = await api.getVoiceStatus();
        setStatus(data);
        applyVoice(info.name);
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setCloning(false);
        if (fileRef.current) fileRef.current.value = "";
      }
    },
    [applyVoice],
  );

  const submitTyped = useCallback(() => {
    const text = typed.trim();
    if (!text) return;
    setTyped("");
    askMentor(
      text,
      {
        onDelta: (chunk) => {
          fullReplyRef.current += chunk;
          setReply(stripTags(fullReplyRef.current));
        },
        onDone: () => undefined,
        onError: (detail) => setError(detail),
      },
      { voice: true },
    );
    setPhase("thinking");
  }, [askMentor, typed, setPhase]);

  if (!open) return null;

  return (
    <div className="voice-overlay" role="dialog" aria-label="Голосовой ассистент">
      <div className="voice-overlay-top">
        <div className="voice-brand">
          <span className="voice-brand-dot" />
          Голосовой ассистент
        </div>
        <button className="voice-icon-btn" onClick={onClose} title="Закрыть">
          <X size={18} />
        </button>
      </div>

      <div className="voice-stage" data-phase={phase}>
        <VoiceOrb phase={phase} levelRef={levelRef} />
        <div className="voice-phase">
          {phase === "thinking" && <Loader2 size={15} className="spin" />}
          {phase === "listening" && <Mic size={15} />}
          <span>{PHASE_LABEL[phase]}</span>
        </div>
      </div>

      <div className="voice-captions">
        {heard && <p className="voice-heard">{heard}</p>}
        {reply && <p className="voice-reply">{reply}</p>}
        {!reply && !heard && (
          <p className="voice-idle-hint">Говорите — я отвечу голосом и текстом.</p>
        )}
      </div>

      {error && (
        <p className="voice-error">
          <AlertTriangle size={14} /> {error}
        </p>
      )}

      {!supported && (
        <div className="voice-fallback">
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitTyped();
            }}
            placeholder="Распознавание речи недоступно. Введите запрос…"
          />
          <button onClick={submitTyped}>Отправить</button>
        </div>
      )}

      <div className="voice-controls">
        <div className="voice-picker">
          {pickerOpen && (
            <div
              className="voice-picker-backdrop"
              onClick={() => setPickerOpen(false)}
            />
          )}
          <button
            className="voice-picker-btn"
            onClick={() => setPickerOpen((prev) => !prev)}
            disabled={!status}
          >
            <span className="voice-picker-label">{currentVoiceTitle}</span>
            <ChevronDown size={15} />
          </button>
          {pickerOpen && (
            <div className="voice-picker-pop" role="listbox">
              <div className="voice-picker-search">
                <Search size={14} />
                <input
                  autoFocus
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") setPickerOpen(false);
                  }}
                  placeholder="Поиск голоса…"
                />
              </div>
              <div className="voice-picker-list">
                {filteredVoices.length === 0 && (
                  <p className="voice-picker-empty">Ничего не найдено</p>
                )}
                {filteredVoices.map((item) => (
                  <button
                    key={item.name}
                    className="voice-picker-item"
                    data-active={item.name === voice}
                    onClick={() => {
                      applyVoice(item.name);
                      setPickerOpen(false);
                    }}
                  >
                    <span className="voice-picker-item-title">{item.title}</span>
                    {item.kind === "cloned" && (
                      <span className="voice-picker-badge">копия</span>
                    )}
                    {item.name === voice && <Check size={14} />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*"
          hidden
          onChange={(event) => void cloneFromFile(event.target.files?.[0])}
        />
        <button
          className="voice-stop-btn"
          title="Клонировать голос из записи"
          onClick={() => fileRef.current?.click()}
          disabled={cloning}
        >
          {cloning ? <Loader2 size={15} className="spin" /> : <Plus size={16} />}
        </button>
        <button
          className="voice-stop-btn"
          onClick={() => {
            ttsRef.current?.cancel();
            playerRef.current?.cancel();
            pendingRef.current = 0;
            streamDoneRef.current = true;
            setPhase("listening");
          }}
          title="Прервать ответ"
        >
          <Square size={15} />
        </button>
      </div>
    </div>
  );
}
