import { useEffect, useRef, useState } from "react";
import { Bell, ChevronDown, Moon, PanelLeft, PanelRight, Sun } from "lucide-react";
import { api, type EventDto } from "../api";

interface TopBarProps {
  title: string;
  brandLabel: string;
  contextConfigured: boolean;
  theme: "light" | "dark";
  sidebarCollapsed: boolean;
  rightOpen: boolean;
  onToggleSidebar: () => void;
  onToggleRight: () => void;
  onOpenContext: () => void;
  onToggleTheme: () => void;
}

function todayIso(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

function formatTime(minute: number): string {
  return `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
}

export function TopBar({
  title,
  brandLabel,
  contextConfigured,
  theme,
  sidebarCollapsed,
  rightOpen,
  onToggleSidebar,
  onToggleRight,
  onOpenContext,
  onToggleTheme,
}: TopBarProps) {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<EventDto[]>([]);
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    api
      .listEvents()
      .then((all) => {
        if (!alive) return;
        const today = todayIso();
        setEvents(
          all
            .filter((event) => event.date === today)
            .sort((a, b) => a.start - b.start),
        );
      })
      .catch(() => {
        /* notifications are best-effort */
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const handler = (event: MouseEvent) => {
      if (!popoverRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="icon-btn topbar-toggle"
          title={sidebarCollapsed ? "Развернуть меню" : "Свернуть меню"}
          onClick={onToggleSidebar}
        >
          <PanelLeft size={17} />
        </button>
        <div className="topbar-heading">
          <span className="topbar-sub">{brandLabel}</span>
          <span className="topbar-title">
            {title}
            <ChevronDown size={15} />
          </span>
        </div>
      </div>
      <div className="topbar-right">
        <button
          className="icon-btn"
          title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
          onClick={onToggleTheme}
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <button
          className="icon-btn topbar-toggle"
          title={rightOpen ? "Скрыть панель" : "Показать панель"}
          onClick={onToggleRight}
        >
          <PanelRight size={17} />
        </button>
        <button
          className={`context-pill${contextConfigured ? "" : " warning"}`}
          title={contextConfigured ? "Контекст ИИ настроен" : "Настроить контекст ИИ"}
          onClick={onOpenContext}
        >
          <span className="context-dot" />
          {contextConfigured ? "Контекст настроен" : "Настроить контекст"}
        </button>
        <div className="notif-wrap" ref={popoverRef}>
          <button
            className="icon-btn"
            title="Напоминания на сегодня"
            onClick={() => setOpen((prev) => !prev)}
          >
            <Bell size={17} />
            {events.length > 0 && <span className="notif-badge">{events.length}</span>}
          </button>
          {open && (
            <div className="notif-popover">
              <div className="notif-title">Сегодня</div>
              {events.length === 0 ? (
                <p className="notif-empty">На сегодня напоминаний нет</p>
              ) : (
                events.map((event) => (
                  <div key={event.id} className="notif-item">
                    <span className="notif-time">{formatTime(event.start)}</span>
                    <span className="notif-text">{event.title}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
