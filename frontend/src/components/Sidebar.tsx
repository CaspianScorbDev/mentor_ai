import { useMemo, useState } from "react";
import {
  ChevronsLeft,
  ChevronsRight,
  Search,
  Settings,
  Sparkles,
  SquarePen,
  Trash2,
  X,
} from "lucide-react";
import type { Chat, Section } from "../types";
import { NAV_ITEMS, formatDialogTime } from "../navigation";

interface SidebarProps {
  chats: Chat[];
  activeChatId: number | null;
  section: Section;
  userName: string;
  userPlan: string;
  initials: string;
  collapsed: boolean;
  onToggle: () => void;
  onSelectSection: (section: Section) => void;
  onSelectChat: (chat: Chat) => void;
  onDeleteChat: (chat: Chat) => void;
  onNewChat: () => void;
}

export function Sidebar({
  chats,
  activeChatId,
  section,
  userName,
  userPlan,
  initials,
  collapsed,
  onToggle,
  onSelectSection,
  onSelectChat,
  onDeleteChat,
  onNewChat,
}: SidebarProps) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");

  const visibleChats = useMemo(() => {
    if (!query.trim()) return chats;
    const needle = query.trim().toLowerCase();
    return chats.filter((chat) => (chat.title ?? "Новый диалог").toLowerCase().includes(needle));
  }, [chats, query]);

  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
      <div className="sidebar-logo">
        <span className="brand-mark">
          <Sparkles size={17} />
        </span>
        <span className="brand-name">AidaMentor</span>
        <button
          className="icon-btn sidebar-toggle"
          title={collapsed ? "Развернуть меню" : "Свернуть меню"}
          onClick={onToggle}
        >
          {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`nav-item${section === item.id ? " active" : ""}`}
              title={collapsed ? item.label : undefined}
              onClick={() => onSelectSection(item.id)}
            >
              <Icon size={17} />
              <span className="nav-label">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {!collapsed && (
        <>
          <div className="sidebar-divider" />

          <div className="dialogs-header">
            <span className="dialogs-title">Диалоги</span>
            <div className="dialogs-actions">
              <button
                className="icon-btn"
                title="Поиск"
                onClick={() => {
                  setSearchOpen((prev) => !prev);
                  if (searchOpen) setQuery("");
                }}
              >
                <Search size={16} />
              </button>
              <button className="icon-btn" title="Новый диалог" onClick={onNewChat}>
                <SquarePen size={16} />
              </button>
            </div>
          </div>

          {searchOpen && (
            <div className="dialogs-search">
              <Search size={14} />
              <input
                autoFocus
                className="dialogs-search-input"
                placeholder="Поиск диалогов"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              {query && (
                <button className="dialogs-search-clear" onClick={() => setQuery("")}>
                  <X size={13} />
                </button>
              )}
            </div>
          )}

          <div className="dialogs-list">
            {visibleChats.length === 0 && (
              <p className="empty-hint">{query ? "Ничего не найдено" : "Пока нет диалогов"}</p>
            )}
            {visibleChats.map((chat) => (
              <div
                key={chat.id}
                className={`dialog-item${activeChatId === chat.id ? " active" : ""}`}
              >
                <button className="dialog-open" onClick={() => onSelectChat(chat)}>
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
        </>
      )}

      <div className="user-profile">
        <span className="avatar" title={userName}>
          {initials}
        </span>
        <div className="user-meta">
          <div className="user-name">{userName}</div>
          <div className="user-plan">{userPlan}</div>
        </div>
        <button className="icon-btn" title="Настройки" onClick={() => onSelectSection("more")}>
          <Settings size={16} />
        </button>
      </div>
    </aside>
  );
}
