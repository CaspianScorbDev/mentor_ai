import type { PlanStage } from "./types";

export const STAGES: { id: PlanStage; label: string }[] = [
  { id: "ideas", label: "Идеи" },
  { id: "progress", label: "В работе" },
  { id: "review", label: "На проверке" },
  { id: "done", label: "Готово" },
];
