export type MessageRole = "ai" | "user" | "system";

export interface SourceItem {
  title: string;
  url: string;
  snippet: string;
}

export interface Message {
  id: number;
  role: MessageRole;
  content: string;
  thinking: string | null;
  sources: SourceItem[] | null;
  created_at: string;
}

export interface Chat {
  id: number;
  title: string | null;
  ai_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface ChatDetail extends Chat {
  messages: Message[];
}

export interface AiPersona {
  id: number;
  provider: string;
  model: string;
  name: string;
  role: string;
  character: string;
  temperature: number;
}

export type Section = "chat" | "schedule" | "plans" | "integrations" | "more";
