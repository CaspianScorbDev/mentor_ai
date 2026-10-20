import { CalendarDays, MessageSquare, MoreHorizontal, Plug, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { Section } from "./types";

export interface NavItem {
  id: Section;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Чат", icon: MessageSquare },
  { id: "schedule", label: "Расписание", icon: CalendarDays },
  { id: "plans", label: "Планы", icon: Target },
  { id: "integrations", label: "Интеграции", icon: Plug },
  { id: "more", label: "Ещё", icon: MoreHorizontal },
];

export const MOBILE_NAV_ITEMS: NavItem[] = [
  { id: "chat", label: "Чат", icon: MessageSquare },
  { id: "schedule", label: "Расписание", icon: CalendarDays },
  { id: "plans", label: "Планы", icon: Target },
  { id: "more", label: "Ещё", icon: MoreHorizontal },
];

export function formatDialogTime(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const sameDay =
    date.getDate() === now.getDate() &&
    date.getMonth() === now.getMonth() &&
    date.getFullYear() === now.getFullYear();

  if (sameDay) {
    return date.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}
