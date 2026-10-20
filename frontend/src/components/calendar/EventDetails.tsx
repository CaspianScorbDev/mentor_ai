import { CalendarDays, Clock, Tag, Trash2, X } from "lucide-react";
import type { CalendarEvent } from "./types";
import { CATEGORY_META, formatDuration, minutesToTime } from "./utils";

interface EventDetailsProps {
  event: CalendarEvent;
  onClose: () => void;
  onDelete: (id: number) => void;
}

function formatDate(dateKey: string): string {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
  });
}

export function EventDetails({ event, onClose, onDelete }: EventDetailsProps) {
  const meta = CATEGORY_META[event.category];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">Событие</span>
          <button className="icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="detail-title-row">
          <span className="detail-bar" style={{ background: meta.color }} />
          <h3 className="detail-title">{event.title}</h3>
        </div>

        <div className="detail-list">
          <div className="detail-row">
            <CalendarDays size={16} />
            {formatDate(event.date)}
          </div>
          <div className="detail-row">
            <Clock size={16} />
            {minutesToTime(event.start)} · {formatDuration(event.duration)}
          </div>
          <div className="detail-row">
            <Tag size={16} />
            <span className="cal-mobile-tag" style={{ background: meta.soft, color: meta.color }}>
              {meta.label}
            </span>
          </div>
        </div>

        {event.detail && <p className="detail-note">{event.detail}</p>}

        <div className="modal-actions">
          <button className="ghost-btn danger" onClick={() => onDelete(event.id)}>
            <Trash2 size={15} />
            Удалить
          </button>
          <button className="primary-btn" onClick={onClose}>
            Готово
          </button>
        </div>
      </div>
    </div>
  );
}
