import { Sparkles, Trash2, X } from "lucide-react";
import type { Chat, Section } from "../types";
import { NAV_ITEMS, formatDialogTime } from "../navigation";

interface MobileMenuProps {
  chats: Chat[];
  activeChatId: number | null;
  section: Section;
  onSelectSection: (section: Section) => void;
  onSelectChat: (chat: Chat) => void;
  onDeleteChat: (chat: Chat) => void;
  onClose: () => void;
}

export function MobileMenu({
  chats,
  activeChatId,
  section,
  onSelectSection,
  onSelectChat,
  onDeleteChat,
  onClose,
}: MobileMenuProps) {
  return (
    <div className="mobile-menu">
      <div className="mobile-menu-header">
        <span className="brand-name" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span className="brand-mark">
            <Sparkles size={17} />
          </span>
          AidaMentor
        </span>
        <button className="icon-btn" title="Закрыть" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="mobile-menu-list">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`mobile-menu-item${section === item.id ? " active" : ""}`}
              onClick={() => {
                onSelectSection(item.id);
                onClose();
              }}
            >
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="sidebar-divider" />

      <div className="dialogs-header">
        <span className="dialogs-title">Диалоги</span>
      </div>
      <div className="dialogs-list">
        {chats.length === 0 && <p className="empty-hint">Пока нет диалогов</p>}
        {chats.map((chat) => (
          <div key={chat.id} className={`dialog-item${activeChatId === chat.id ? " active" : ""}`}>
            <button
              className="dialog-open"
              onClick={() => {
                onSelectChat(chat);
                onClose();
              }}
            >
              <span className="dialog-name">{chat.title || "Новый диалог"}</span>
              <span className="dialog-time">{formatDialogTime(chat.updated_at)}</span>
            </button>
            <button
              className="dialog-delete"
              title="Удалить диалог"
              onClick={() => onDeleteChat(chat)}
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
