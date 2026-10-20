export type EventCategory = "personal" | "work" | "aida";
export type CalendarView = "day" | "week" | "month";

export interface CalendarEvent {
  id: number;
  title: string;
  date: string;
  start: number;
  duration: number;
  category: EventCategory;
  detail?: string;
}
