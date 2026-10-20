import { useEffect, useMemo, useState } from "react";
import { Check, Clock, Mail, Plus, Send, TrendingUp } from "lucide-react";
import { api, type EventDto, type SettingsDto, type TaskDto } from "../api";
import { pomodoro } from "../pomodoro";
import { Pomodoro } from "./Pomodoro";
import type { Section } from "../types";

function formatDate(): { weekday: string; main: string } {
  const now = new Date();
  const weekday = now.toLocaleDateString("ru-RU", { weekday: "long" });
  const main = now.toLocaleDateString("ru-RU", { day: "numeric", month: "long" });
  return { weekday: weekday.charAt(0).toUpperCase() + weekday.slice(1), main };
}

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function minuteOfDay(): number {
  const now = new Date();
  return now.getHours() * 60 + now.getMinutes();
}

function formatTime(minute: number): string {
  return `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
}

interface RightPanelProps {
  onPickRecommendation: (text: string) => void;
  onSelectSection: (section: Section) => void;
}

export function RightPanel({ onPickRecommendation, onSelectSection }: RightPanelProps) {
  const date = formatDate();
  const [events, setEvents] = useState<EventDto[]>([]);
  const [settings, setSettings] = useState<SettingsDto | null>(null);
  const [tasks, setTasks] = useState<TaskDto[]>([]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.listEvents(), api.getSettings(), api.listTasks()])
      .then(([eventList, settingsData, taskList]) => {
        if (!alive) return;
        setEvents(eventList);
        setSettings(settingsData);
        setTasks(taskList);
      })
      .catch(() => {
        /* the chat still works without the panel data */
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (settings) pomodoro.syncFocusMinutes(settings.pomodoro_minute);
  }, [settings]);

  const today = todayIso();
  const nowMinute = minuteOfDay();
  const todayEvents = useMemo(
    () =>
      events
        .filter((event) => event.date === today)
        .sort((a, b) => a.start - b.start),
    [events, today],
  );

  const totalTasks = tasks.length;
  const doneTasks = tasks.filter((task) => task.stage === "done").length;
  const progressPercent = totalTasks > 0 ? Math.round((doneTasks / totalTasks) * 100) : 0;

  const recommendation = useMemo(() => {
    const upcoming = todayEvents.filter((event) => event.start + event.duration > nowMinute);
    const next = upcoming[0];
    if (!next) {
      return todayEvents.length === 0
        ? "Календарь на сегодня пуст. Предлагаю забронировать фокус-блок и продвинуть главную цель."
        : "Все события дня позади — хорошее время подвести итоги и спланировать завтра.";
    }
    const gap = next.start - nowMinute;
    if (gap > 20) {
      return `До «${next.title}» ещё ${gap} мин. Предлагаю вклинить короткий фокус-блок на 15 минут.`;
    }
    return `Следующее событие — «${next.title}» в ${formatTime(next.start)}. Подготовить тезисы?`;
  }, [todayEvents, nowMinute]);

  return (
    <aside className="right-panel">
      <div className="panel-block">
        <div className="date-block">
          <div>
            <div className="date-weekday">{date.weekday}</div>
            <div className="date-main">{date.main}</div>
          </div>
          <button
            className="add-task-btn"
            title="Добавить задачу"
            onClick={() => onSelectSection("plans")}
          >
            <Plus size={17} />
          </button>
        </div>

        <div>
          {todayEvents.length === 0 && (
            <div className="event-empty">На сегодня событий нет</div>
          )}
          {todayEvents.map((event) => {
            const done = event.start + event.duration <= nowMinute;
            const meta = [
              `${formatTime(event.start)}–${formatTime(event.start + event.duration)}`,
              event.detail,
            ]
              .filter(Boolean)
              .join(" · ");
            return (
              <div key={event.id} className={`event${done ? " done" : ""}`}>
                <span className="event-time">{formatTime(event.start)}</span>
                <span className="event-divider" />
                <div className="event-body">
                  <div className="event-name">{event.title}</div>
                  <div className="event-meta">{meta}</div>
                </div>
                {done && (
                  <span className="event-status">
                    <Check size={15} />
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <Pomodoro />

      <div className="panel-block">
        <div className="section-header">
          <span className="section-title">Интеграции</span>
          <button className="link-btn" onClick={() => onSelectSection("integrations")}>
            Настроить
          </button>
        </div>
        <div className="integrations-card">
          <div className="integration">
            <span className="integration-icon">
              <Send size={16} />
            </span>
            <div className="integration-body">
              <div className="integration-name">Telegram</div>
              <div className="integration-sub">
                {settings?.telegram_enabled ? "Напоминания подключены" : "Выключены"}
              </div>
            </div>
            <span className={`status-dot${settings?.telegram_enabled ? " on" : ""}`} />
          </div>
          <div className="integration">
            <span className="integration-icon">
              <Mail size={16} />
            </span>
            <div className="integration-body">
              <div className="integration-name">Email-дайджест</div>
              <div className="integration-sub">
                {settings?.email_digest_enabled
                  ? `Каждый день в ${settings.digest_time}`
                  : "Выключен"}
              </div>
            </div>
            <span className={`status-dot${settings?.email_digest_enabled ? " on" : ""}`} />
          </div>
        </div>
      </div>

      <div className="recommendation">
        <div className="rec-head">
          <span className="rec-icon">
            <TrendingUp size={14} />
          </span>
          <span className="rec-title">Рекомендация Aida</span>
        </div>
        <p className="rec-text">{recommendation}</p>
        <button
          className="rec-action"
          onClick={() => onPickRecommendation("Помоги перестроить день с учётом расписания")}
        >
          Перепланировать день
        </button>
      </div>

      <div className="panel-block">
        <div className="section-header">
          <span className="section-title">Прогресс целей</span>
          <span className="link-btn">
            <Clock size={13} /> {doneTasks} из {totalTasks}
          </span>
        </div>
        <div className="progress-track">
          <span className="progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
      </div>
    </aside>
  );
}
