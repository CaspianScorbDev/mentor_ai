import type { CalendarEvent } from "./types";
import {
  CATEGORY_META,
  WEEKDAYS_SHORT,
  formatDuration,
  isSameDay,
  minutesToTime,
  toDateKey,
  weekDays,
} from "./utils";

interface MobileDayListProps {
  selected: Date;
  events: CalendarEvent[];
  onSelectDate: (date: Date) => void;
  onSelectEvent: (event: CalendarEvent) => void;
}

export function MobileDayList({
  selected,
  events,
  onSelectDate,
  onSelectEvent,
}: MobileDayListProps) {
  const days = weekDays(selected);
  const today = new Date();
  const key = toDateKey(selected);
  const dayEvents = events
    .filter((event) => event.date === key)
    .sort((a, b) => a.start - b.start);

  return (
    <div className="cal-mobile">
      <div className="cal-mobile-strip">
        {days.map((day) => (
          <button
            key={toDateKey(day)}
            className={`cal-mobile-day${isSameDay(day, selected) ? " active" : ""}${
              isSameDay(day, today) ? " today" : ""
            }`}
            onClick={() => onSelectDate(day)}
          >
            <span className="cal-mobile-weekday">
              {WEEKDAYS_SHORT[(day.getDay() + 6) % 7]}
            </span>
            <span className="cal-mobile-num">{day.getDate()}</span>
          </button>
        ))}
      </div>

      <div className="cal-mobile-list">
        {dayEvents.length === 0 && <p className="empty-hint">На этот день событий нет</p>}
        {dayEvents.map((event) => {
          const meta = CATEGORY_META[event.category];
          return (
            <button
              key={event.id}
              className="cal-mobile-item"
              onClick={() => onSelectEvent(event)}
            >
              <span className="cal-mobile-time">{minutesToTime(event.start)}</span>
              <span className="cal-mobile-bar" style={{ background: meta.color }} />
              <span className="cal-mobile-body">
                <span className="cal-mobile-title">{event.title}</span>
                <span className="cal-mobile-meta">
                  <span className="cal-mobile-tag" style={{ background: meta.soft, color: meta.color }}>
                    {meta.label}
                  </span>
                  {formatDuration(event.duration)}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
