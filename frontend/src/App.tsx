import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  editMessage,
  regenerateMessage,
  streamMessage,
  type ContextDto,
  type SourceItem,
  type StreamOptions,
} from "./api";
import type { Chat, ChatDetail, Message, Section } from "./types";
import { useMediaQuery } from "./hooks";
import { setPomodoroReporter } from "./pomodoro";
import { NAV_ITEMS } from "./navigation";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { ChatView } from "./components/ChatView";
import { VoiceOverlay, type AskMentor } from "./components/VoiceOverlay";
import { RightPanel } from "./components/RightPanel";
import { MobileHeader } from "./components/MobileHeader";
import { MobileNav } from "./components/MobileNav";
import { MobileMenu } from "./components/MobileMenu";

const Settings = lazy(() =>
  import("./components/Settings").then((module) => ({ default: module.Settings })),
);
const Calendar = lazy(() =>
  import("./components/calendar/Calendar").then((module) => ({ default: module.Calendar })),
);
const Plans = lazy(() =>
  import("./components/plans/Plans").then((module) => ({ default: module.Plans })),
);
const Integrations = lazy(() =>
  import("./components/Integrations").then((module) => ({ default: module.Integrations })),
);

function SectionFallback() {
  return <div className="section-fallback">Загрузка…</div>;
}

function greetingForHour(hour: number): string {
  if (hour < 6) return "Доброй ночи";
  if (hour < 12) return "Доброе утро";
  if (hour < 18) return "Добрый день";
  return "Добрый вечер";
}

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "AM";
  return parts
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");
}

type Theme = "light" | "dark";
const THEME_KEY = "aida-theme";
const SIDEBAR_KEY = "aida-sidebar-collapsed";
const RIGHT_PANEL_KEY = "aida-right-panel";

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* storage may be unavailable */
  }
  return "dark";
}

function readFlag(key: string, fallback: boolean): boolean {
  try {
    const stored = localStorage.getItem(key);
    if (stored === "1") return true;
    if (stored === "0") return false;
  } catch {
    /* storage may be unavailable */
  }
  return fallback;
}

function writeFlag(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* storage may be unavailable */
  }
}

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeChat, setActiveChat] = useState<ChatDetail | null>(null);
  const [streaming, setStreaming] = useState<string | null>(null);
  const [streamingThinking, setStreamingThinking] = useState<string | null>(null);
  const [streamingSources, setStreamingSources] = useState<SourceItem[] | null>(null);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [section, setSection] = useState<Section>("chat");
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [context, setContext] = useState<ContextDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(readTheme);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => readFlag(SIDEBAR_KEY, false));
  const [rightOpen, setRightOpen] = useState(() => readFlag(RIGHT_PANEL_KEY, true));

  const isMobile = useMediaQuery("(max-width: 820px)");
  const activeChatRef = useRef<ChatDetail | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    activeChatRef.current = activeChat;
  }, [activeChat]);

  useEffect(() => {
    setPomodoroReporter((phase, minutes) => {
      void api.notifyPomodoro(phase, minutes).catch(() => {
        /* Telegram reminders are optional */
      });
    });
    return () => setPomodoroReporter(null);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* storage may be unavailable */
    }
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      writeFlag(SIDEBAR_KEY, !prev);
      return !prev;
    });
  }, []);

  const toggleRightPanel = useCallback(() => {
    setRightOpen((prev) => {
      writeFlag(RIGHT_PANEL_KEY, !prev);
      return !prev;
    });
  }, []);

  const userName = context?.user_name.trim() || "Гость";
  const initials = useMemo(() => initialsFor(userName), [userName]);
  const mentorMode = context?.mentor_mode ?? true;

  const refreshChats = useCallback(async () => {
    try {
      setChats(await api.listChats());
    } catch {
      /* backend may be unavailable; keep current list */
    }
  }, []);

  const loadContext = useCallback(async () => {
    try {
      setContext(await api.getContext());
    } catch {
      /* context is optional for the chat to work */
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch
    void refreshChats();
    void loadContext();
  }, [refreshChats, loadContext]);

  useEffect(() => {
    if (!error) return;
    const id = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(id);
  }, [error]);

  const selectChat = useCallback(async (chat: Chat) => {
    setSection("chat");
    setStreaming(null);
    setVoiceOpen(false);
    try {
      setActiveChat(await api.getChat(chat.id));
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const newChat = useCallback(() => {
    setSection("chat");
    setActiveChat(null);
    setStreaming(null);
    setVoiceOpen(false);
  }, []);

  const deleteChat = useCallback(
    async (chat: Chat) => {
      const title = chat.title || "Новый диалог";
      if (!window.confirm(`Удалить диалог «${title}»? Это действие нельзя отменить.`)) return;

      try {
        await api.deleteChat(chat.id);
      } catch (err) {
        setError((err as Error).message);
        return;
      }

      if (activeChatRef.current?.id === chat.id) {
        setActiveChat(null);
        setStreaming(null);
        setVoiceOpen(false);
      }
      setChats((prev) => prev.filter((item) => item.id !== chat.id));
    },
    [],
  );

  const toggleMentorMode = useCallback(async () => {
    if (!context) return;
    const next = !context.mentor_mode;
    setContext({ ...context, mentor_mode: next });
    try {
      setContext(await api.updateContext({ mentor_mode: next }));
    } catch (err) {
      setError((err as Error).message);
      setContext((prev) => (prev ? { ...prev, mentor_mode: !next } : prev));
    }
  }, [context]);

  const resetStream = useCallback(() => {
    setStreaming(null);
    setStreamingThinking(null);
    setStreamingSources(null);
    setStreamStatus(null);
    setBusy(false);
  }, []);

  const submitRequest = useCallback(
    (
      chatId: number,
      handlers: Parameters<AskMentor>[1],
      options: StreamOptions | undefined,
      call: (signal: AbortSignal, handlers: Parameters<AskMentor>[1]) => Promise<void>,
    ) => {
      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      setSection("chat");
      setBusy(true);
      setStreaming("");
      setStreamingThinking(null);
      setStreamingSources(null);
      setStreamStatus(null);

      void (async () => {
        try {
          await call(controller.signal, handlers);
        } catch (err) {
          if ((err as Error).name !== "AbortError") {
            handlers.onError((err as Error).message);
          } else {
            handlers.onDone(null);
          }
        } finally {
          if (abortRef.current === controller) abortRef.current = null;
          void refreshChats();
        }
      })();
      void chatId;
      void options;
    },
    [refreshChats],
  );

  const askMentor = useCallback<AskMentor>(
    (text, handlers, options) => {
      void (async () => {
        let chat = activeChatRef.current;
        try {
          if (!chat) {
            const created = await api.createChat(text.slice(0, 60));
            chat = created;
            setActiveChat(created);
            setChats((prev) => [created, ...prev]);
          }
          const userMessage: Message = {
            id: -Date.now(),
            role: "user",
            content: text,
            thinking: null,
            sources: null,
            created_at: new Date().toISOString(),
          };
          setActiveChat((prev) =>
            prev ? { ...prev, messages: [...prev.messages, userMessage] } : prev,
          );

          const activeChatId = chat.id;
          submitRequest(
            activeChatId,
            handlers,
            options,
            (signal, wrapped) =>
              streamMessage(
                activeChatId,
                text,
                {
                  onDelta: wrapped.onDelta,
                  onThinking: wrapped.onThinking,
                  onSources: wrapped.onSources,
                  onStatus: wrapped.onStatus,
                  onDone: (message) => {
                    const aiMessage = message as Message | null;
                    setActiveChat((prev) =>
                      prev
                        ? {
                            ...prev,
                            messages: aiMessage
                              ? [...prev.messages, aiMessage]
                              : prev.messages,
                          }
                        : prev,
                    );
                    wrapped.onDone(aiMessage);
                  },
                  onError: wrapped.onError,
                },
                signal,
                options,
              ),
          );
        } catch (err) {
          handlers.onError((err as Error).message);
        }
      })();
    },
    [submitRequest],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    resetStream();
  }, [resetStream]);

  const streamHandlers = useCallback(
    (): Parameters<AskMentor>[1] => ({
      onDelta: (chunk) => setStreaming((prev) => (prev ?? "") + chunk),
      onThinking: (chunk) => setStreamingThinking((prev) => (prev ?? "") + chunk),
      onSources: (items) => setStreamingSources(items),
      onStatus: (detail) => setStreamStatus(detail),
      onDone: () => resetStream(),
      onError: (detail) => {
        setError(detail);
        resetStream();
      },
    }),
    [resetStream],
  );

  const send = useCallback(
    (text: string, options?: StreamOptions) => {
      if (busy) return;
      askMentor(text, streamHandlers(), options);
    },
    [askMentor, busy, streamHandlers],
  );

  const regenerate = useCallback(
    (options?: StreamOptions) => {
      const chat = activeChatRef.current;
      if (!chat || busy) return;
      submitRequest(chat.id, streamHandlers(), options, (signal, wrapped) =>
        regenerateMessage(
          chat.id,
          {
            ...wrapped,
            onDone: (message) => {
              const aiMessage = message as Message | null;
              setActiveChat((prev) => {
                if (!prev || !aiMessage) return prev;
                const messages = [...prev.messages];
                let lastUser = -1;
                for (let i = messages.length - 1; i >= 0; i -= 1) {
                  if (messages[i].role === "user") {
                    lastUser = i;
                    break;
                  }
                }
                return { ...prev, messages: [...messages.slice(0, lastUser + 1), aiMessage] };
              });
              wrapped.onDone(aiMessage);
            },
          },
          signal,
          options,
        ),
      );
    },
    [busy, submitRequest, streamHandlers],
  );

  const editAndResend = useCallback(
    (message: Message, text: string, options?: StreamOptions) => {
      const chat = activeChatRef.current;
      if (!chat || busy) return;
      setActiveChat((prev) => {
        if (!prev) return prev;
        const index = prev.messages.findIndex((item) => item.id === message.id);
        if (index < 0) return prev;
        const edited: Message = { ...prev.messages[index], content: text };
        return { ...prev, messages: [...prev.messages.slice(0, index), edited] };
      });
      submitRequest(chat.id, streamHandlers(), options, (signal, wrapped) =>
        editMessage(
          chat.id,
          message.id,
          text,
          {
            ...wrapped,
            onDone: (message2) => {
              const aiMessage = message2 as Message | null;
              setActiveChat((prev) =>
                prev
                  ? {
                      ...prev,
                      messages: aiMessage ? [...prev.messages, aiMessage] : prev.messages,
                    }
                  : prev,
              );
              wrapped.onDone(aiMessage);
            },
          },
          signal,
          options,
        ),
      );
    },
    [busy, submitRequest, streamHandlers],
  );

  const sectionLabel = NAV_ITEMS.find((item) => item.id === section)?.label ?? "Чат";
  const topbarTitle = section === "chat" ? activeChat?.title || "Новый диалог" : sectionLabel;

  return (
    <div className="app">
      {!isMobile && (
        <Sidebar
          chats={chats}
          activeChatId={activeChat?.id ?? null}
          section={section}
          userName={userName}
          userPlan="Личный план"
          initials={initials}
          collapsed={sidebarCollapsed}
          onToggle={toggleSidebar}
          onSelectSection={setSection}
          onSelectChat={selectChat}
          onDeleteChat={deleteChat}
          onNewChat={newChat}
        />
      )}

      <div className="main">
        {isMobile ? (
          <MobileHeader title={topbarTitle} initials={initials} onOpenMenu={() => setMenuOpen(true)} />
        ) : (
          <TopBar
            title={topbarTitle}
            brandLabel="Личный наставник"
            contextConfigured={context?.configured ?? false}
            theme={theme}
            sidebarCollapsed={sidebarCollapsed}
            rightOpen={rightOpen}
            onToggleSidebar={toggleSidebar}
            onToggleRight={toggleRightPanel}
            onOpenContext={() => setSection("more")}
            onToggleTheme={toggleTheme}
          />
        )}

        <div className="main-body">
          {section === "chat" ? (
            <>
              <ChatView
                messages={activeChat?.messages ?? []}
                streaming={streaming}
                streamingThinking={streamingThinking}
                streamingSources={streamingSources}
                streamStatus={streamStatus}
                busy={busy}
                mentorMode={mentorMode}
                greeting={`${greetingForHour(new Date().getHours())}, ${userName.split(" ")[0]}`}
                question="Чем помочь сегодня?"
                caption="Я ваш личный наставник — помогу разобраться в задачах, спланировать день и не потерять фокус."
                onSend={send}
                onToggleVoice={() => setVoiceOpen((prev) => !prev)}
                onToggleMentorMode={() => void toggleMentorMode()}
                onStop={stop}
                onRegenerate={regenerate}
                onEdit={editAndResend}
              />
              {!isMobile && rightOpen && (
                <RightPanel onPickRecommendation={send} onSelectSection={setSection} />
              )}
            </>
          ) : section === "schedule" ? (
            <Suspense fallback={<SectionFallback />}>
              <Calendar />
            </Suspense>
          ) : section === "plans" ? (
            <Suspense fallback={<SectionFallback />}>
              <Plans />
            </Suspense>
          ) : section === "integrations" ? (
            <Suspense fallback={<SectionFallback />}>
              <Integrations />
            </Suspense>
          ) : (
            <Suspense fallback={<SectionFallback />}>
              <Settings
                context={context}
                userName={userName}
                theme={theme}
                onContextChange={setContext}
                onToggleTheme={toggleTheme}
              />
            </Suspense>
          )}
        </div>

        {isMobile && <MobileNav section={section} onSelectSection={setSection} />}
      </div>

      {isMobile && menuOpen && (
        <MobileMenu
          chats={chats}
          activeChatId={activeChat?.id ?? null}
          section={section}
          onSelectSection={setSection}
          onSelectChat={selectChat}
          onDeleteChat={deleteChat}
          onClose={() => setMenuOpen(false)}
        />
      )}

      <VoiceOverlay
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        askMentor={askMentor}
      />

      {error && <div className="toast">{error}</div>}
    </div>
  );
}
