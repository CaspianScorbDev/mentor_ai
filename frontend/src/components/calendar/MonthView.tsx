import type { CalendarEvent } from "./types";
import { CATEGORY_META, WEEKDAYS_SHORT, isSameDay, monthMatrix, toDateKey } from "./utils";

interface MonthViewProps {
  anchor: Date;
  events: CalendarEvent[];
  onSelectDate: (date: Date) => void;
  onSelectEvent: (event: CalendarEvent) => void;
}

export function MonthView({ anchor, events, onSelectDate, onSelectEvent }: MonthViewProps) {
  const days = monthMatrix(anchor);
  const today = new Date();

  return (
    <div className="cal-month">
      <div className="cal-month-head">
        {WEEKDAYS_SHORT.map((day) => (
          <span key={day} className="cal-month-weekday">
            {day}
          </span>
        ))}
      </div>
      <div className="cal-month-grid">
        {days.map((day) => {
          const key = toDateKey(day);
          const dayEvents = events.filter((event) => event.date === key);
          const outside = day.getMonth() !== anchor.getMonth();
          return (
            <button
              key={key}
              className={`cal-month-cell${outside ? " outside" : ""}${
                isSameDay(day, today) ? " today" : ""
              }`}
              onClick={() => onSelectDate(day)}
            >
              <span className="cal-month-num">{day.getDate()}</span>
              <span className="cal-month-events">
                {dayEvents.slice(0, 3).map((event) => {
                  const meta = CATEGORY_META[event.category];
                  return (
                    <span
                      key={event.id}
                      className="cal-chip"
                      style={{ background: meta.soft, color: meta.color }}
                      onClick={(event2) => {
                        event2.stopPropagation();
                        onSelectEvent(event);
                      }}
                    >
                      <span className="cal-chip-dot" style={{ background: meta.color }} />
                      {event.title}
                    </span>
                  );
                })}
                {dayEvents.length > 3 && (
                  <span className="cal-chip-more">+{dayEvents.length - 3}</span>
                )}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
