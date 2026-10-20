import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Bot,
  Brain,
  Check,
  Code,
  FileText,
  Globe,
  Mic,
  Paperclip,
  Plus,
  Square,
  X,
} from "lucide-react";
import type { StreamOptions } from "../api";

interface ComposerProps {
  busy: boolean;
  mentorMode: boolean;
  onToggleMentorMode: () => void;
  onSend: (text: string, options?: StreamOptions) => void;
  onToggleVoice: () => void;
  onStop: () => void;
}

interface Attachment {
  name: string;
  size: number;
  excerpt: string | null;
  truncated: boolean;
}

type ExtensionKey = "webSearch" | "codeMode" | "filesMode";

const TEXT_EXTENSIONS =
  /\.(txt|md|markdown|csv|tsv|json|log|ya?ml|toml|ini|env|ts|tsx|js|jsx|py|rb|go|rs|java|kt|swift|c|cc|cpp|h|hpp|cs|php|html?|css|scss|sh|sql|xml)$/i;
const MAX_EXCERPT = 4000;

const EXTENSIONS: {
  key: ExtensionKey;
  icon: typeof Globe;
  label: string;
  desc: string;
}[] = [
  { key: "webSearch", icon: Globe, label: "Поиск по интернету", desc: "Ответ на основе свежих данных" },
  { key: "codeMode", icon: Code, label: "Код", desc: "Рабочий код без заглушек" },
  { key: "filesMode", icon: FileText, label: "Файлы", desc: "Глубокий анализ прикреплённого" },
];

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function isTextual(file: File): boolean {
  return file.type.startsWith("text/") || TEXT_EXTENSIONS.test(file.name);
}

async function readAttachment(file: File): Promise<Attachment> {
  const base: Attachment = { name: file.name, size: file.size, excerpt: null, truncated: false };
  if (!isTextual(file)) return base;

  const raw = await file.text();
  const truncated = raw.length > MAX_EXCERPT;
  return {
    ...base,
    excerpt: truncated ? raw.slice(0, MAX_EXCERPT) : raw,
    truncated,
  };
}

export function Composer({
  busy,
  mentorMode,
  onToggleMentorMode,
  onSend,
  onToggleVoice,
  onStop,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [deepThinking, setDeepThinking] = useState(false);
  const [extensions, setExtensions] = useState<Record<ExtensionKey, boolean>>({
    webSearch: false,
    codeMode: false,
    filesMode: false,
  });
  const [menuOpen, setMenuOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const clearAttachment = () => {
    setAttachment(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const pickFile = async (file: File | null | undefined) => {
    if (!file) return;
    const next = await readAttachment(file);
    setAttachment(next);
    setExtensions((prev) => (prev.filesMode ? prev : { ...prev, filesMode: true }));
    setMenuOpen(false);
  };

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    let payload = text;
    if (attachment) {
      const header = `📎 Файл: ${attachment.name} (${humanSize(attachment.size)})`;
      payload = attachment.excerpt
        ? `${text}\n\n${header}\n\`\`\`\n${attachment.excerpt}${attachment.truncated ? "\n… (файл обрезан)" : ""}\n\`\`\``
        : `${text}\n\n${header} — содержимое недоступно, файл прикреплён только по названию.`;
    }
    onSend(payload, {
      deepThinking,
      webSearch: extensions.webSearch,
      codeMode: extensions.codeMode,
      filesMode: extensions.filesMode && attachment !== null,
    });
    setValue("");
    clearAttachment();
  };

  const toggleExtension = (key: ExtensionKey) => {
    setExtensions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const activeCount = Object.values(extensions).filter(Boolean).length;

  return (
    <div className="composer-wrap">
      <div className="composer">
        {attachment && (
          <div className="attachment-chip">
            <Paperclip size={13} />
            <span>
              {attachment.name} · {humanSize(attachment.size)}
            </span>
            <button className="attachment-remove" title="Убрать файл" onClick={clearAttachment}>
              <X size={13} />
            </button>
          </div>
        )}
        <div className="composer-row">
          <button
            className="voice-launch"
            title="Голосовой ассистент"
            onClick={onToggleVoice}
            aria-label="Голосовой ассистент"
          >
            <Mic size={18} />
            <span className="voice-launch-glow" />
          </button>
          <textarea
            ref={textareaRef}
            className="composer-input"
            rows={1}
            placeholder="Напишите сообщение или задайте вопрос..."
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
          />
        </div>
        <div className="composer-toolbar">
          <div className="composer-left">
            <input
              ref={fileRef}
              type="file"
              hidden
              onChange={(event) => void pickFile(event.target.files?.[0])}
            />
            <div className="ext-anchor" ref={menuRef}>
              <button
                className={`tool-btn${activeCount ? " on" : ""}`}
                title="Расширения"
                aria-expanded={menuOpen}
                onClick={() => setMenuOpen((open) => !open)}
              >
                <Plus size={17} />
                {activeCount > 0 && <span className="tool-badge">{activeCount}</span>}
              </button>
              {menuOpen && (
                <div className="ext-menu" role="menu">
                  <div className="ext-menu-title">Расширения</div>
                  {EXTENSIONS.map(({ key, icon: Icon, label, desc }) => (
                    <button
                      key={key}
                      role="menuitemcheckbox"
                      aria-checked={extensions[key]}
                      className={`ext-item${extensions[key] ? " checked" : ""}`}
                      onClick={() => {
                        if (key === "filesMode") {
                          const next = !extensions.filesMode;
                          setExtensions((prev) => ({ ...prev, filesMode: next }));
                          if (next && !attachment) fileRef.current?.click();
                        } else {
                          toggleExtension(key);
                        }
                      }}
                    >
                      <span className="ext-icon">
                        <Icon size={15} />
                      </span>
                      <span className="ext-text">
                        <span className="ext-label">{label}</span>
                        <span className="ext-desc">{desc}</span>
                      </span>
                      <span className="ext-check">{extensions[key] && <Check size={14} />}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              className="tool-btn"
              title="Прикрепить файл"
              onClick={() => fileRef.current?.click()}
            >
              <Paperclip size={17} />
            </button>
            <button
              className={`mode-toggle${deepThinking ? " active" : ""}`}
              title="Глубокое мышление: модель тщательнее продумывает ответ (ответ дольше)"
              onClick={() => setDeepThinking((on) => !on)}
            >
              <Brain size={16} />
              <span>Глубокое мышление</span>
            </button>
            <button
              className={`mode-toggle${mentorMode ? " active" : ""}`}
              title="Режим наставника: конкретные шаги и контроль прогресса"
              onClick={onToggleMentorMode}
            >
              <Bot size={16} />
              <span>Режим наставника</span>
            </button>
          </div>
          <div className="composer-right">
            {busy ? (
              <button className="send-btn stop" title="Остановить" onClick={onStop}>
                <Square size={15} fill="currentColor" />
              </button>
            ) : (
              <button
                className="send-btn"
                title="Отправить"
                onClick={submit}
                disabled={value.trim().length === 0}
              >
                <ArrowUp size={18} />
              </button>
            )}
          </div>
        </div>
      </div>
      <p className="disclaimer">Aida может ошибаться. Проверяйте важную информацию.</p>
    </div>
  );
}
