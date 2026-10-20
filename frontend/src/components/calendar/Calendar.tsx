import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, ChevronLeft, ChevronRight, Clock } from "lucide-react";
import { useClock, useMediaQuery } from "../../hooks";
import { api, type EventDto } from "../../api";
import type { CalendarEvent, CalendarView, EventCategory } from "./types";
import { CATEGORY_META, CATEGORY_ORDER, MONTHS, addDays, addMonths, weekDays } from "./utils";
import { TimeGrid } from "./TimeGrid";
import { MonthView } from "./MonthView";
import { MobileDayList } from "./MobileDayList";
import { EventModal } from "./EventModal";
import { EventDetails } from "./EventDetails";

const VIEW_LABELS: Record<CalendarView, string> = {
  day: "День",
  week: "Неделя",
  month: "Месяц",
};

function mapEvent(dto: EventDto): CalendarEvent {
  return {
    id: dto.id,
    title: dto.title,
    date: dto.date,
    start: dto.start,
    duration: dto.duration,
    category: dto.category,
    detail: dto.detail ?? undefined,
  };
}

function rangeLabel(view: CalendarView, cursor: Date): string {
  if (view === "month") {
    return `${MONTHS[cursor.getMonth()]} ${cursor.getFullYear()}`;
  }
  if (view === "day") {
    return cursor.toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
  }
  const days = weekDays(cursor);
  const first = days[0];
  const last = days[6];
  const sameMonth = first.getMonth() === last.getMonth();
  const head = `${first.getDate()} ${sameMonth ? "" : `${MONTHS[first.getMonth()]} `}– ${last.getDate()} ${MONTHS[last.getMonth()]}`;
  return head.replace(/\s+/g, " ");
}

export function Calendar() {
  const [view, setView] = useState<CalendarView>("week");
  const [cursor, setCursor] = useState(() => new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [active, setActive] = useState<Set<EventCategory>>(
    () => new Set(CATEGORY_ORDER),
  );
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<CalendarEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const now = useClock();
  const isMobile = useMediaQuery("(max-width: 820px)");

  useEffect(() => {
    let alive = true;
    api
      .listEvents()
      .then((dtos) => {
        if (alive) setEvents(dtos.map(mapEvent));
      })
      .catch((err: unknown) => {
        if (alive) setError((err as Error).message);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!error) return;
    const id = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(id);
  }, [error]);

  const visibleEvents = useMemo(
    () => events.filter((event) => active.has(event.category)),
    [events, active],
  );

  const step = (direction: number) => {
    setCursor((prev) => {
      if (view === "day") return addDays(prev, direction);
      if (view === "week") return addDays(prev, direction * 7);
      return addMonths(prev, direction);
    });
  };

  const toggleCategory = (category: EventCategory) => {
    setActive((prev) => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };

  const createEvent = async (event: Omit<CalendarEvent, "id">) => {
    try {
      const dto = await api.createEvent({
        title: event.title,
        date: event.date,
        start: event.start,
        duration: event.duration,
        category: event.category,
        detail: event.detail ?? null,
      });
      setEvents((prev) => [...prev, mapEvent(dto)]);
      setActive((prev) => new Set(prev).add(dto.category));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const deleteEvent = async (id: number) => {
    try {
      await api.deleteEvent(id);
      setEvents((prev) => prev.filter((event) => event.id !== id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSelected(null);
    }
  };

  const clockLabel = now.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="calendar">
      <div className="cal-toolbar">
        <div className="cal-toolbar-main">
          <div className="cal-nav">
            <button className="icon-btn" onClick={() => step(-1)} title="Назад">
              <ChevronLeft size={18} />
            </button>
            <button className="today-btn" onClick={() => setCursor(new Date())}>
              Сегодня
            </button>
            <button className="icon-btn" onClick={() => step(1)} title="Вперёд">
              <ChevronRight size={18} />
            </button>
          </div>
          <span className="cal-label">{rangeLabel(view, cursor)}</span>
          <span className="cal-clock">
            <Clock size={14} />
            {clockLabel}
          </span>
        </div>

        <div className="cal-toolbar-sub">
          <div className="view-switch">
            {(Object.keys(VIEW_LABELS) as CalendarView[]).map((id) => (
              <button
                key={id}
                className={`view-tab${view === id ? " active" : ""}`}
                onClick={() => setView(id)}
              >
                {VIEW_LABELS[id]}
              </button>
            ))}
          </div>

          <div className="cat-filters">
            {CATEGORY_ORDER.map((id) => {
              const meta = CATEGORY_META[id];
              return (
                <button
                  key={id}
                  className={`filter-chip${active.has(id) ? " active" : ""}`}
                  style={active.has(id) ? { borderColor: meta.color, color: meta.color } : undefined}
                  onClick={() => toggleCategory(id)}
                >
                  <span className="cat-dot" style={{ background: meta.color }} />
                  {meta.label}
                </button>
              );
            })}
          </div>

          <button className="primary-btn" onClick={() => setCreating(true)}>
            <CalendarPlus size={16} />
            Событие
          </button>
        </div>
      </div>

      <div className="cal-viewport">
        {isMobile ? (
          <MobileDayList
            selected={cursor}
            events={visibleEvents}
            onSelectDate={setCursor}
            onSelectEvent={setSelected}
          />
        ) : view === "month" ? (
          <MonthView
            anchor={cursor}
            events={visibleEvents}
            onSelectDate={(date) => {
              setCursor(date);
              setView("day");
            }}
            onSelectEvent={setSelected}
          />
        ) : (
          <TimeGrid
            days={view === "day" ? [cursor] : weekDays(cursor)}
            events={visibleEvents}
            onSelectEvent={setSelected}
          />
        )}
      </div>

      {creating && (
        <EventModal
          defaultDate={cursor}
          onClose={() => setCreating(false)}
          onCreate={createEvent}
        />
      )}
      {selected && (
        <EventDetails event={selected} onClose={() => setSelected(null)} onDelete={deleteEvent} />
      )}
      {error && <div className="toast">{error}</div>}
    </div>
  );
}
