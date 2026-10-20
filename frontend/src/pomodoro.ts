import { useSyncExternalStore } from "react";

export type PomodoroPhase = "focus" | "break";

export interface PomodoroSnapshot {
  phase: PomodoroPhase;
  running: boolean;
  remainingMs: number;
  focusMin: number;
  breakMin: number;
  cyclesToday: number;
  completedTotal: number;
  custom: boolean;
}

const STORAGE_KEY = "aida-pomodoro";
const DEFAULT_FOCUS_MIN = 25;
const DEFAULT_BREAK_MIN = 5;
const MIN_MINUTES = 1;
const MAX_MINUTES = 180;

interface PersistedState {
  phase: PomodoroPhase;
  running: boolean;
  endAt: number | null;
  remainingMs: number;
  focusMin: number;
  breakMin: number;
  cyclesToday: number;
  cyclesDate: string;
  completedTotal: number;
  custom: boolean;
}

function dayKey(now = new Date()): string {
  return `${now.getFullYear()}-${now.getMonth() + 1}-${now.getDate()}`;
}

function clampMinutes(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_FOCUS_MIN;
  return Math.min(MAX_MINUTES, Math.max(MIN_MINUTES, Math.round(value)));
}

function phaseMs(phase: PomodoroPhase, focusMin: number, breakMin: number): number {
  return (phase === "focus" ? focusMin : breakMin) * 60_000;
}

function defaults(): PersistedState {
  return {
    phase: "focus",
    running: false,
    endAt: null,
    remainingMs: DEFAULT_FOCUS_MIN * 60_000,
    focusMin: DEFAULT_FOCUS_MIN,
    breakMin: DEFAULT_BREAK_MIN,
    cyclesToday: 0,
    cyclesDate: dayKey(),
    completedTotal: 0,
    custom: false,
  };
}

function load(): PersistedState {
  const base = defaults();
  let raw: string | null;
  try {
    raw = localStorage.getItem(STORAGE_KEY);
  } catch {
    return base;
  }
  if (!raw) return base;
  let parsed: Partial<PersistedState>;
  try {
    parsed = JSON.parse(raw) as Partial<PersistedState>;
  } catch {
    return base;
  }
  const focusMin = clampMinutes(parsed.focusMin ?? base.focusMin);
  const breakMin = clampMinutes(parsed.breakMin ?? base.breakMin);
  const phase: PomodoroPhase = parsed.phase === "break" ? "break" : "focus";
  const today = dayKey();
  const cyclesToday = parsed.cyclesDate === today ? Number(parsed.cyclesToday) || 0 : 0;
  const running = Boolean(parsed.running);
  const endAt = typeof parsed.endAt === "number" ? parsed.endAt : null;
  let remainingMs =
    typeof parsed.remainingMs === "number"
      ? Math.max(0, parsed.remainingMs)
      : phaseMs(phase, focusMin, breakMin);
  if (running && endAt !== null) {
    remainingMs = Math.max(0, endAt - Date.now());
  }
  return {
    phase,
    running: running && endAt !== null,
    endAt: running && endAt !== null ? endAt : null,
    remainingMs,
    focusMin,
    breakMin,
    cyclesToday,
    cyclesDate: today,
    completedTotal: Number(parsed.completedTotal) || 0,
    custom: Boolean(parsed.custom),
  };
}

let state: PersistedState = load();
let snapshot: PomodoroSnapshot = build();
const listeners = new Set<() => void>();
let ticker: number | null = null;
let reporter: ((phase: PomodoroPhase, minutes: number) => void) | null = null;

export function setPomodoroReporter(
  fn: ((phase: PomodoroPhase, minutes: number) => void) | null,
): void {
  reporter = fn;
}

function build(): PomodoroSnapshot {
  return {
    phase: state.phase,
    running: state.running,
    remainingMs: state.remainingMs,
    focusMin: state.focusMin,
    breakMin: state.breakMin,
    cyclesToday: state.cyclesToday,
    completedTotal: state.completedTotal,
    custom: state.custom,
  };
}

function persist(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* storage may be unavailable */
  }
}

function ensureTicker(): void {
  if (typeof window === "undefined") return;
  if (state.running && ticker === null) {
    ticker = window.setInterval(tick, 1000);
  } else if (!state.running && ticker !== null) {
    window.clearInterval(ticker);
    ticker = null;
  }
}

function apply(partial: Partial<PersistedState>): void {
  state = {
    ...state,
    ...partial,
    cyclesDate: partial.cyclesDate ?? dayKey(),
  };
  snapshot = build();
  persist();
  ensureTicker();
  listeners.forEach((listener) => listener());
}

function beep(): void {
  try {
    const Ctx: typeof AudioContext | undefined =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.18, ctx.currentTime + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.6);
    osc.start();
    osc.stop(ctx.currentTime + 0.65);
    osc.onended = () => void ctx.close();
  } catch {
    /* audio is best-effort */
  }
}

function notify(phase: PomodoroPhase): void {
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(phase === "focus" ? "Фокус-сессия завершена" : "Перерыв закончился", {
      body:
        phase === "focus"
          ? "Пора отдохнуть — сделайте короткий перерыв."
          : "Готовы к новой фокус-сессии?",
      tag: "aida-pomodoro",
    });
  } catch {
    /* notifications are best-effort */
  }
}

function advance(counted: boolean): void {
  const finished = state.phase;
  const isFocus = finished === "focus";
  const nextPhase: PomodoroPhase = isFocus ? "break" : "focus";
  const nextRemaining = phaseMs(nextPhase, state.focusMin, state.breakMin);
  apply({
    phase: nextPhase,
    running: false,
    endAt: null,
    remainingMs: nextRemaining,
    cyclesToday: counted && isFocus ? state.cyclesToday + 1 : state.cyclesToday,
    completedTotal: counted && isFocus ? state.completedTotal + 1 : state.completedTotal,
  });
  if (!counted) return;
  notify(finished);
  beep();
  const minutes = finished === "focus" ? state.focusMin : state.breakMin;
  reporter?.(finished, minutes);
}

function complete(): void {
  advance(true);
}

function skip(): void {
  advance(false);
}

function tick(): void {
  if (!state.running || state.endAt === null) return;
  const remaining = state.endAt - Date.now();
  if (remaining <= 0) {
    complete();
    return;
  }
  apply({ remainingMs: remaining });
}

function requestPermission(): void {
  if (typeof Notification === "undefined") return;
  if (Notification.permission === "default") void Notification.requestPermission();
}

export function requestNotificationPermission(): void {
  requestPermission();
}

export const pomodoro = {
  start(): void {
    requestPermission();
    if (state.running) return;
    const fallback = phaseMs(state.phase, state.focusMin, state.breakMin);
    const remaining = state.remainingMs > 0 ? state.remainingMs : fallback;
    apply({ running: true, endAt: Date.now() + remaining, remainingMs: remaining });
  },
  pause(): void {
    if (!state.running || state.endAt === null) return;
    apply({ running: false, endAt: null, remainingMs: Math.max(0, state.endAt - Date.now()) });
  },
  toggle(): void {
    if (state.running) {
      pomodoro.pause();
    } else {
      pomodoro.start();
    }
  },
  reset(): void {
    apply({
      running: false,
      endAt: null,
      remainingMs: phaseMs(state.phase, state.focusMin, state.breakMin),
    });
  },
  skip(): void {
    skip();
  },
  setFocusMinutes(minutes: number, fromUser = false): void {
    const value = clampMinutes(minutes);
    const idle = !state.running && state.phase === "focus";
    const untouched = Math.abs(state.remainingMs - state.focusMin * 60_000) < 1000;
    apply({
      focusMin: value,
      custom: fromUser ? true : state.custom,
      remainingMs: idle && untouched ? value * 60_000 : state.remainingMs,
    });
  },
  setBreakMinutes(minutes: number): void {
    apply({ breakMin: clampMinutes(minutes) });
  },
  syncFocusMinutes(minutes: number): void {
    if (state.custom) return;
    pomodoro.setFocusMinutes(minutes, false);
  },
};

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): PomodoroSnapshot {
  return snapshot;
}

export function usePomodoro(): PomodoroSnapshot {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") tick();
  });
}

if (state.running && state.endAt !== null && state.endAt <= Date.now()) {
  complete();
} else {
  ensureTicker();
}
