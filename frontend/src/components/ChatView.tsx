import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  CalendarClock,
  Check,
  ChevronDown,
  Compass,
  Globe,
  Loader2,
  Pencil,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import type { Message } from "../types";
import type { SourceItem, StreamOptions } from "../api";
import { Composer } from "./Composer";
import { CopyMessageButton, Markdown } from "./Markdown";

interface ChatViewProps {
  messages: Message[];
  streaming: string | null;
  streamingThinking: string | null;
  streamingSources: SourceItem[] | null;
  streamStatus: string | null;
  busy: boolean;
  mentorMode: boolean;
  greeting: string;
  question: string;
  caption: string;
  onSend: (text: string, options?: StreamOptions) => void;
  onToggleVoice: () => void;
  onToggleMentorMode: () => void;
  onStop: () => void;
  onRegenerate: (options?: StreamOptions) => void;
  onEdit: (message: Message, text: string, options?: StreamOptions) => void;
}

const SCENARIOS = [
  {
    icon: Compass,
    title: "Разбери сложную тему",
    desc: "Объясню простыми словами и проверю понимание на примерах",
  },
  {
    icon: CalendarClock,
    title: "Составь план на неделю",
    desc: "Разобью цели на шаги и расставлю приоритеты по дням",
  },
  {
    icon: Sparkles,
    title: "Подготовься к встрече",
    desc: "Соберу тезисы, вопросы и возможные возражения",
  },
];

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function ThinkingBlock({ text, streaming }: { text: string; streaming: boolean }) {
  const [open, setOpen] = useState(streaming);
  const bodyRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (streaming && open && bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [text, streaming, open]);

  return (
    <div className={`thinking-block${streaming ? " live" : ""}`}>
      <button className="thinking-head" onClick={() => setOpen((prev) => !prev)}>
        {streaming ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
        <span>{streaming ? "Размышляю…" : "Ход рассуждений"}</span>
        <ChevronDown size={14} className={`thinking-chevron${open ? " open" : ""}`} />
      </button>
      {open && (
        <div className="thinking-body" ref={bodyRef}>
          {text}
          {streaming && <span className="caret" />}
        </div>
      )}
    </div>
  );
}

function SourcesList({ items }: { items: SourceItem[] }) {
  return (
    <div className="sources">
      <div className="sources-title">
        <Globe size={13} />
        <span>Источники</span>
      </div>
      <div className="sources-grid">
        {items.map((item, index) => (
          <a
            key={`${item.url}-${index}`}
            className="source-card"
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            title={item.snippet}
          >
            <span className="source-num">{index + 1}</span>
            <span className="source-body">
              <span className="source-domain">{hostOf(item.url)}</span>
              <span className="source-title">{item.title}</span>
            </span>
          </a>
        ))}
      </div>
    </div>
  );
}

function AiLabel({ children }: { children?: ReactNode }) {
  return (
    <span className="message-label">
      <span className="ai-avatar-sm">
        <Sparkles size={11} />
      </span>
      {children ?? "Aida"}
    </span>
  );
}

export function ChatView({
  messages,
  streaming,
  streamingThinking,
  streamingSources,
  streamStatus,
  busy,
  mentorMode,
  greeting,
  question,
  caption,
  onSend,
  onToggleVoice,
  onToggleMentorMode,
  onStop,
  onRegenerate,
  onEdit,
}: ChatViewProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const isEmpty = messages.length === 0 && streaming === null;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming, streamingThinking, streamingSources, streamStatus]);

  const lastAiIndex = messages.reduce(
    (acc, message, index) => (message.role === "ai" ? index : acc),
    -1,
  );

  const startEdit = (message: Message) => {
    setEditingId(message.id);
    setDraft(message.content);
  };

  const commitEdit = () => {
    const text = draft.trim();
    const message = messages.find((item) => item.id === editingId);
    setEditingId(null);
    if (message && text) onEdit(message, text);
  };

  return (
    <section className="chat-area">
      <div className="chat-scroll">
        {isEmpty ? (
          <div className="welcome">
            <span className="ai-symbol">
              <Sparkles size={26} />
            </span>
            <div className="welcome-head">
              <span className="welcome-greeting">{greeting}</span>
              <h1 className="welcome-question">{question}</h1>
              <p className="welcome-caption">{caption}</p>
            </div>
            <div className="scenario-grid">
              {SCENARIOS.map((scenario) => {
                const Icon = scenario.icon;
                return (
                  <button
                    key={scenario.title}
                    className="scenario-card"
                    onClick={() => onSend(scenario.title)}
                  >
                    <span className="scenario-icon">
                      <Icon size={17} />
                    </span>
                    <span className="scenario-title">{scenario.title}</span>
                    <span className="scenario-desc">{scenario.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="messages">
            {messages.map((message, index) => {
              const isLastAi = index === lastAiIndex && !busy;
              if (message.role === "user" && editingId === message.id) {
                return (
                  <div key={message.id} className="message user editing">
                    <span className="message-label">Вы</span>
                    <div className="edit-box">
                      <textarea
                        className="edit-input"
                        autoFocus
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            commitEdit();
                          }
                          if (e.key === "Escape") setEditingId(null);
                        }}
                      />
                      <div className="edit-actions">
                        <button className="ghost-btn sm" onClick={() => setEditingId(null)}>
                          <X size={14} />
                          Отмена
                        </button>
                        <button className="primary-btn sm" onClick={commitEdit}>
                          <Check size={14} />
                          Отправить
                        </button>
                      </div>
                    </div>
                  </div>
                );
              }
              return (
                <div key={message.id} className={`message ${message.role === "user" ? "user" : "ai"}`}>
                  {message.role === "ai" ? <AiLabel /> : <span className="message-label">Вы</span>}
                  {message.role === "ai" && message.thinking && (
                    <ThinkingBlock text={message.thinking} streaming={false} />
                  )}
                  {message.role === "ai" && message.sources && message.sources.length > 0 && (
                    <SourcesList items={message.sources} />
                  )}
                  <div className="message-bubble">
                    {message.role === "ai" ? (
                      <Markdown content={message.content} />
                    ) : (
                      message.content
                    )}
                  </div>
                  <div className="message-actions">
                    <CopyMessageButton text={message.content} />
                    {message.role === "user" && !busy && (
                      <button
                        className="message-copy"
                        title="Изменить и отправить заново"
                        onClick={() => startEdit(message)}
                      >
                        <Pencil size={13} />
                        Изменить
                      </button>
                    )}
                    {message.role === "ai" && isLastAi && (
                      <button
                        className="message-copy"
                        title="Сгенерировать ответ заново"
                        onClick={() => onRegenerate()}
                      >
                        <RefreshCw size={13} />
                        Заново
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            {streaming !== null && (
              <div className="message ai">
                <AiLabel />
                {streamStatus && (
                  <div className="stream-status">
                    <Loader2 size={13} className="spin" />
                    <span>{streamStatus}</span>
                  </div>
                )}
                {streamingThinking && (
                  <ThinkingBlock text={streamingThinking} streaming />
                )}
                {streamingSources && streamingSources.length > 0 && (
                  <SourcesList items={streamingSources} />
                )}
                <div className="message-bubble">
                  <Markdown content={streaming} />
                  <span className="caret" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <Composer
        busy={busy}
        mentorMode={mentorMode}
        onToggleMentorMode={onToggleMentorMode}
        onSend={onSend}
        onToggleVoice={onToggleVoice}
        onStop={onStop}
      />
    </section>
  );
}
