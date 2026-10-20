import { useEffect, useRef } from "react";
import type { CalendarEvent } from "./types";
import {
  CATEGORY_META,
  WEEKDAYS_SHORT,
  isSameDay,
  minutesToTime,
  nowMinutes,
  toDateKey,
} from "./utils";

const HOUR_HEIGHT = 52;
const HOURS = Array.from({ length: 24 }, (_, index) => index);

interface TimeGridProps {
  days: Date[];
  events: CalendarEvent[];
  onSelectEvent: (event: CalendarEvent) => void;
}

export function TimeGrid({ days, events, onSelectEvent }: TimeGridProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const today = new Date();

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 7 * HOUR_HEIGHT - 8;
    }
  }, []);

  return (
    <div className="cal-grid">
      <div className="cal-head">
        <div className="cal-gutter-head" />
        {days.map((day) => (
          <div
            key={toDateKey(day)}
            className={`cal-day-head${isSameDay(day, today) ? " today" : ""}`}
          >
            <span className="cal-day-name">{WEEKDAYS_SHORT[(day.getDay() + 6) % 7]}</span>
            <span className="cal-day-num">{day.getDate()}</span>
          </div>
        ))}
      </div>

      <div className="cal-scroll" ref={scrollRef}>
        <div className="cal-body">
          <div className="cal-gutter">
            {HOURS.map((hour) => (
              <div key={hour} className="cal-hour-label" style={{ height: HOUR_HEIGHT }}>
                {hour > 0 ? `${String(hour).padStart(2, "0")}:00` : ""}
              </div>
            ))}
          </div>

          <div className="cal-cols">
            {days.map((day) => {
              const dayKey = toDateKey(day);
              const dayEvents = events.filter((event) => event.date === dayKey);
              const isToday = isSameDay(day, today);
              return (
                <div key={dayKey} className="cal-col">
                  {HOURS.map((hour) => (
                    <div key={hour} className="cal-cell" style={{ height: HOUR_HEIGHT }} />
                  ))}

                  {dayEvents.map((event) => {
                    const meta = CATEGORY_META[event.category];
                    return (
                      <button
                        key={event.id}
                        className="cal-event"
                        onClick={() => onSelectEvent(event)}
                        style={{
                          top: (event.start / 60) * HOUR_HEIGHT + 1,
                          height: Math.max((event.duration / 60) * HOUR_HEIGHT - 3, 22),
                          background: meta.soft,
                          borderColor: meta.color,
                          color: meta.color,
                        }}
                      >
                        <span className="cal-event-title">{event.title}</span>
                        <span className="cal-event-time">
                          {minutesToTime(event.start)}
                        </span>
                      </button>
                    );
                  })}

                  {isToday && (
                    <div
                      className="cal-now"
                      style={{ top: (nowMinutes(today) / 60) * HOUR_HEIGHT }}
                    >
                      <span className="cal-now-dot" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
