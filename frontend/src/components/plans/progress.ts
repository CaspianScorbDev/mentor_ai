import type { PlanStage, PlanTask } from "./types";

const STAGE_BASE: Record<PlanStage, number> = {
  ideas: 8,
  progress: 45,
  review: 75,
  done: 100,
};

export function taskProgress(task: PlanTask): number {
  if (task.stage === "done") return 100;
  const total = task.subtasks.length;
  const ratio = total ? task.subtasks.filter((item) => item.done).length / total : 0;
  return Math.round((STAGE_BASE[task.stage] + ratio * 100) / 2);
}

export function goalProgress(tasks: PlanTask[]): number {
  if (tasks.length === 0) return 0;
  const total = tasks.reduce((sum, task) => sum + taskProgress(task), 0);
  return Math.round(total / tasks.length);
}

export function pace(progress: number, daysLeft: number, totalDays = 60): string {
  const elapsed = totalDays - daysLeft;
  const expected = (elapsed / totalDays) * 100;
  const delta = progress - expected;
  if (delta >= 5) return "опережаете график";
  if (delta <= -5) return "немного отстаёте";
  return "в графике";
}
