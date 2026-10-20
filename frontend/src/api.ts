import type { Chat, ChatDetail, AiPersona, SourceItem } from "./types";

const ROOT = (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://localhost:8000";
const BASE = `${ROOT.replace(/\/$/, "")}/api/v1`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function formRequest<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { method: "POST", body: form });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type EventCategoryDto = "personal" | "work" | "aida";
export type PlanStageDto = "ideas" | "progress" | "review" | "done";

export interface EventDto {
  id: number;
  title: string;
  date: string;
  start: number;
  duration: number;
  category: EventCategoryDto;
  detail: string | null;
}

export interface EventInput {
  title: string;
  date: string;
  start: number;
  duration: number;
  category: EventCategoryDto;
  detail?: string | null;
}

export interface GoalDto {
  id: number;
  title: string;
  description: string;
  deadline: string | null;
}

export interface GoalInput {
  title?: string;
  description?: string;
  deadline?: string | null;
}

export interface ProjectInput {
  title?: string;
  description?: string;
  deadline?: string | null;
}

export interface SubtaskDto {
  id: number;
  title: string;
  done: boolean;
}

export interface TaskDto {
  id: number;
  title: string;
  stage: PlanStageDto;
  category: EventCategoryDto;
  goal_id: number | null;
  deadline: string | null;
  assignee: string | null;
  subtasks: SubtaskDto[];
}

export interface TaskInput {
  title: string;
  stage: PlanStageDto;
  category: EventCategoryDto;
  goal_id?: number | null;
  deadline?: string | null;
  assignee?: string | null;
}

export interface SettingsDto {
  telegram_enabled: boolean;
  telegram_chat_id: string | null;
  email_digest_enabled: boolean;
  email_address: string | null;
  digest_time: string;
  pomodoro_minute: number;
  telegram_configured: boolean;
  email_configured: boolean;
}

export interface ContextDto {
  user_name: string;
  current_goal: string;
  specialization: string;
  communication_style: string;
  mentor_tone: string;
  interests: string;
  language: string;
  mentor_mode: boolean;
  use_schedule: boolean;
  use_plans: boolean;
  configured: boolean;
}

export type ContextInput = Partial<Omit<ContextDto, "configured">>;

export interface IntegrationTestDto {
  ok: boolean;
  detail: string;
}

export interface DigestDto {
  body: string;
  channels: [string, string][];
}

export interface AiConfigDto {
  provider: string | null;
  model: string | null;
  temperature: number | null;
  max_tokens: number | null;
  system_prompt: string | null;
  effective_provider: string;
  effective_model: string;
  effective_temperature: number;
  effective_max_tokens: number;
}

export type AiConfigInput = Partial<
  Pick<AiConfigDto, "provider" | "model" | "temperature" | "max_tokens" | "system_prompt">
>;

export interface AiModelInfoDto {
  provider: string;
  model: string;
  label: string;
}

export interface AiModelsDto {
  provider: string;
  models: AiModelInfoDto[];
  error: string | null;
}

export interface VoiceInfoDto {
  name: string;
  title: string;
  kind: "builtin" | "cloned";
  language: string | null;
}

export interface VoiceStatusDto {
  backend: string;
  ready: boolean;
  model: string;
  sample_rate: number;
  default_voice: string | null;
  detail: string | null;
  voices: VoiceInfoDto[];
}

export interface VoiceTranscriptDto {
  text: string;
  language: string | null;
}

export const api = {
  listChats: () => request<Chat[]>("/chats"),

  getChat: (id: number) => request<ChatDetail>(`/chats/${id}`),

  createChat: (title?: string, aiId?: number) =>
    request<ChatDetail>("/chats", {
      method: "POST",
      body: JSON.stringify({ title: title ?? null, ai_id: aiId ?? null }),
    }),

  deleteChat: (id: number) => request<void>(`/chats/${id}`, { method: "DELETE" }),

  listAi: () => request<AiPersona[]>("/ai"),

  listEvents: () => request<EventDto[]>("/schedule/events"),

  createEvent: (payload: EventInput) =>
    request<EventDto>("/schedule/events", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateEvent: (id: number, changes: Partial<EventInput>) =>
    request<EventDto>(`/schedule/events/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  deleteEvent: (id: number) =>
    request<void>(`/schedule/events/${id}`, { method: "DELETE" }),

  getGoal: () => request<GoalDto>("/plans/goal"),

  updateGoal: (changes: GoalInput) =>
    request<GoalDto>("/plans/goal", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  listProjects: () => request<GoalDto[]>("/plans/projects"),

  createProject: (payload: ProjectInput & { title: string }) =>
    request<GoalDto>("/plans/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateProject: (id: number, changes: ProjectInput) =>
    request<GoalDto>(`/plans/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  deleteProject: (id: number) =>
    request<void>(`/plans/projects/${id}`, { method: "DELETE" }),

  listTasks: () => request<TaskDto[]>("/plans/tasks"),

  createTask: (payload: TaskInput) =>
    request<TaskDto>("/plans/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateTask: (id: number, changes: Partial<TaskInput>) =>
    request<TaskDto>(`/plans/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  deleteTask: (id: number) => request<void>(`/plans/tasks/${id}`, { method: "DELETE" }),

  addSubtask: (taskId: number, title: string) =>
    request<TaskDto>(`/plans/tasks/${taskId}/subtasks`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),

  updateSubtask: (id: number, changes: { title?: string; done?: boolean }) =>
    request<SubtaskDto>(`/plans/subtasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  deleteSubtask: (id: number) =>
    request<void>(`/plans/subtasks/${id}`, { method: "DELETE" }),

  getSettings: () => request<SettingsDto>("/settings"),

  updateSettings: (changes: Partial<SettingsDto>) =>
    request<SettingsDto>("/settings", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  testTelegram: () =>
    request<IntegrationTestDto>("/settings/telegram/test", { method: "POST" }),

  testEmail: () => request<IntegrationTestDto>("/settings/email/test", { method: "POST" }),

  getDigest: () => request<DigestDto>("/settings/digest"),

  runDigest: () => request<DigestDto>("/settings/digest/run", { method: "POST" }),

  notifyPomodoro: (phase: "focus" | "break", minutes: number) =>
    request<IntegrationTestDto>("/settings/pomodoro/complete", {
      method: "POST",
      body: JSON.stringify({ phase, minutes }),
    }),

  getContext: () => request<ContextDto>("/context"),

  updateContext: (changes: ContextInput) =>
    request<ContextDto>("/context", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  getAiConfig: () => request<AiConfigDto>("/ai/config"),

  updateAiConfig: (changes: AiConfigInput) =>
    request<AiConfigDto>("/ai/config", {
      method: "PATCH",
      body: JSON.stringify(changes),
    }),

  listAiModels: (provider: string) =>
    request<AiModelsDto>(`/ai/models?provider=${encodeURIComponent(provider)}`),

  getVoiceStatus: () => request<VoiceStatusDto>("/voice/status"),

  transcribeVoice: (file: Blob, language?: string) => {
    const form = new FormData();
    form.append("file", file, "voice.webm");
    if (language) form.append("language", language);
    return formRequest<VoiceTranscriptDto>("/voice/transcribe", form);
  },

  cloneVoice: (file: Blob, name: string, referenceText?: string) => {
    const form = new FormData();
    form.append("file", file, "voice.wav");
    form.append("name", name);
    if (referenceText) form.append("reference_text", referenceText);
    return formRequest<VoiceInfoDto>("/voice/clone", form);
  },

  speakVoice: async (text: string, voice?: string) => {
    const response = await fetch(`${BASE}/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: voice ?? null }),
    });
    if (!response.ok) throw new Error(`Синтез не удался (${response.status})`);
    return response.blob();
  },
};

export type { SourceItem } from "./types";

export interface StreamHandlers {
  onDelta: (chunk: string) => void;
  onDone: (message: unknown) => void;
  onError: (detail: string) => void;
  onThinking?: (chunk: string) => void;
  onSources?: (items: SourceItem[]) => void;
  onStatus?: (detail: string) => void;
}

export interface StreamOptions {
  voice?: boolean;
  deepThinking?: boolean;
  webSearch?: boolean;
  codeMode?: boolean;
  filesMode?: boolean;
}

function flagBody(options?: StreamOptions) {
  return {
    voice: options?.voice ?? false,
    deep_thinking: options?.deepThinking ?? false,
    web_search: options?.webSearch ?? false,
    code_mode: options?.codeMode ?? false,
    files_mode: options?.filesMode ?? false,
  };
}

async function readStream(response: Response, handlers: StreamHandlers): Promise<void> {
  if (!response.ok || !response.body) {
    throw new Error(`Не удалось получить ответ (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const event of events) {
      const line = event.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (!payload) continue;

      const parsed = JSON.parse(payload) as {
        type: string;
        content?: string;
        detail?: string;
        message?: unknown;
        items?: SourceItem[];
      };

      if (parsed.type === "delta" && parsed.content) handlers.onDelta(parsed.content);
      else if (parsed.type === "thinking" && parsed.content)
        handlers.onThinking?.(parsed.content);
      else if (parsed.type === "sources" && parsed.items) handlers.onSources?.(parsed.items);
      else if (parsed.type === "status") handlers.onStatus?.(parsed.detail ?? "");
      else if (parsed.type === "done") handlers.onDone(parsed.message);
      else if (parsed.type === "error") handlers.onError(parsed.detail ?? "Ошибка");
    }
  }
}

export async function streamMessage(
  chatId: number,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  options?: StreamOptions,
): Promise<void> {
  const response = await fetch(`${BASE}/chats/${chatId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, ...flagBody(options) }),
    signal,
  });
  await readStream(response, handlers);
}

export async function regenerateMessage(
  chatId: number,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  options?: StreamOptions,
): Promise<void> {
  const response = await fetch(`${BASE}/chats/${chatId}/messages/regenerate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(flagBody(options)),
    signal,
  });
  await readStream(response, handlers);
}

export async function editMessage(
  chatId: number,
  messageId: number,
  content: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  options?: StreamOptions,
): Promise<void> {
  const response = await fetch(`${BASE}/chats/${chatId}/messages/${messageId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, ...flagBody(options) }),
    signal,
  });
  await readStream(response, handlers);
}
