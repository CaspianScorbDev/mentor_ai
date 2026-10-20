import type { EventCategory } from "../calendar/types";

export type PlanStage = "ideas" | "progress" | "review" | "done";
export type PlanMode = "board" | "map" | "list";

export interface Subtask {
  id: number;
  title: string;
  done: boolean;
}

export interface PlanTask {
  id: number;
  title: string;
  stage: PlanStage;
  category: EventCategory;
  projectId?: number;
  deadline?: string;
  assignee?: string;
  subtasks: Subtask[];
}

export interface MapNode {
  id: string;
  label: string;
  x: number;
  y: number;
  kind: "goal" | "direction" | "task";
  category?: EventCategory;
  done?: boolean;
}

export interface MapLink {
  from: string;
  to: string;
}
