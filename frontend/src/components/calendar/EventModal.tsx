import { useState } from "react";
import { X } from "lucide-react";
import type { CalendarEvent, EventCategory } from "./types";
import { CATEGORY_META, CATEGORY_ORDER, toDateKey } from "./utils";

interface EventModalProps {
  defaultDate: Date;
  onClose: () => void;
  onCreate: (event: Omit<CalendarEvent, "id">) => void;
}

const DURATIONS = [15, 30, 45, 60, 90, 120];

export function EventModal({ defaultDate, onClose, onCreate }: EventModalProps) {
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(toDateKey(defaultDate));
  const [time, setTime] = useState("10:00");
  const [duration, setDuration] = useState(60);
  const [category, setCategory] = useState<EventCategory>("work");

  const submit = () => {
    const trimmed = title.trim();
    if (!trimmed) return;
    const [hours, minutes] = time.split(":").map(Number);
    onCreate({
      title: trimmed,
      date,
      start: hours * 60 + minutes,
      duration,
      category,
    });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">Новое событие</span>
          <button className="icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <label className="field">
          <span className="field-label">Название</span>
          <input
            className="field-input"
            autoFocus
            value={title}
            placeholder="Например, встреча по проекту"
            onChange={(event) => setTitle(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && submit()}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span className="field-label">Дата</span>
            <input
              className="field-input"
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Начало</span>
            <input
              className="field-input"
              type="time"
              value={time}
              onChange={(event) => setTime(event.target.value)}
            />
          </label>
        </div>

        <label className="field">
          <span className="field-label">Длительность</span>
          <select
            className="field-input"
            value={duration}
            onChange={(event) => setDuration(Number(event.target.value))}
          >
            {DURATIONS.map((value) => (
              <option key={value} value={value}>
                {value < 60 ? `${value} мин` : `${value / 60} ч`}
              </option>
            ))}
          </select>
        </label>

        <div className="field">
          <span className="field-label">Категория</span>
          <div className="cat-picker">
            {CATEGORY_ORDER.map((id) => {
              const meta = CATEGORY_META[id];
              return (
                <button
                  key={id}
                  className={`cat-option${category === id ? " active" : ""}`}
                  style={
                    category === id
                      ? { background: meta.soft, color: meta.color, borderColor: meta.color }
                      : undefined
                  }
                  onClick={() => setCategory(id)}
                >
                  <span className="cat-dot" style={{ background: meta.color }} />
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="modal-actions">
          <button className="ghost-btn" onClick={onClose}>
            Отмена
          </button>
          <button className="primary-btn" onClick={submit} disabled={!title.trim()}>
            Создать
          </button>
        </div>
      </div>
    </div>
  );
}
