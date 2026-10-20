import { Coffee, Flame, Pause, Play, RotateCcw, SkipForward, Timer } from "lucide-react";
import { pomodoro, requestNotificationPermission, usePomodoro } from "../pomodoro";

const FOCUS_PRESETS = [15, 25, 45, 60];
const BREAK_PRESETS = [5, 10, 15];

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function formatClock(ms: number): string {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

export function Pomodoro() {
  const p = usePomodoro();
  const isFocus = p.phase === "focus";
  const totalMs = (isFocus ? p.focusMin : p.breakMin) * 60_000;
  const progress = totalMs > 0 ? 1 - p.remainingMs / totalMs : 0;
  const offset = CIRCUMFERENCE * (1 - Math.min(1, Math.max(0, progress)));
  const cyclesIntoSet = p.cyclesToday % 4;

  return (
    <section className={`pomo${p.running ? " running" : ""}${isFocus ? "" : " break"}`}>
      <header className="pomo-head">
        <span className="pomo-phase">
          {isFocus ? <Timer size={15} /> : <Coffee size={15} />}
          {isFocus ? "Фокус" : "Перерыв"}
        </span>
        <span className="pomo-today" title="Завершено сегодня">
          <Flame size={14} />
          {p.cyclesToday}
        </span>
      </header>

      <div className="pomo-ring">
        <svg viewBox="0 0 120 120" className="pomo-svg">
          <circle className="pomo-track" cx="60" cy="60" r={RADIUS} />
          <circle
            className="pomo-progress"
            cx="60"
            cy="60"
            r={RADIUS}
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="pomo-center">
          <span className="pomo-time">{formatClock(p.remainingMs)}</span>
          <span className="pomo-caption">
            {p.running
              ? isFocus
                ? "в работе"
                : "отдыхаем"
              : isFocus
                ? "готовы начать?"
                : "перерыв на паузе"}
          </span>
        </div>
      </div>

      <div className="pomo-actions">
        <button
          className="pomo-ghost"
          title="Сбросить"
          onClick={() => pomodoro.reset()}
          aria-label="Сбросить таймер"
        >
          <RotateCcw size={16} />
        </button>
        <button
          className="pomo-main"
          onClick={() => {
            requestNotificationPermission();
            pomodoro.toggle();
          }}
        >
          {p.running ? <Pause size={18} /> : <Play size={18} />}
          {p.running ? "Пауза" : "Старт"}
        </button>
        <button
          className="pomo-ghost"
          title="Пропустить этап (не засчитывается)"
          onClick={() => pomodoro.skip()}
          aria-label="Пропустить этап"
        >
          <SkipForward size={16} />
        </button>
      </div>

      <div className="pomo-dots" aria-hidden="true">
        {[0, 1, 2, 3].map((index) => (
          <span key={index} className={`pomo-dot${index < cyclesIntoSet ? " on" : ""}`} />
        ))}
        <span className="pomo-dots-label">{p.cyclesToday} за сегодня</span>
      </div>

      {isFocus ? (
        <div className="pomo-presets">
          {FOCUS_PRESETS.map((minutes) => (
            <button
              key={minutes}
              className={`pomo-chip${p.focusMin === minutes ? " on" : ""}`}
              onClick={() => pomodoro.setFocusMinutes(minutes, true)}
            >
              {minutes} мин
            </button>
          ))}
        </div>
      ) : (
        <div className="pomo-presets">
          {BREAK_PRESETS.map((minutes) => (
            <button
              key={minutes}
              className={`pomo-chip${p.breakMin === minutes ? " on" : ""}`}
              onClick={() => pomodoro.setBreakMinutes(minutes)}
            >
              {minutes} мин
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
