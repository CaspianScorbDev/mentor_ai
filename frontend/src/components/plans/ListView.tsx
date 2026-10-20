import { CATEGORY_META } from "../calendar/utils";
import type { PlanTask } from "./types";
import { STAGES } from "./data";
import { taskProgress } from "./progress";

interface ListViewProps {
  tasks: PlanTask[];
  onOpen: (task: PlanTask) => void;
}

export function ListView({ tasks, onOpen }: ListViewProps) {
  return (
    <div className="plan-list">
      {STAGES.map((stage) => {
        const stageTasks = tasks.filter((task) => task.stage === stage.id);
        if (stageTasks.length === 0) return null;
        return (
          <div key={stage.id} className="plan-list-group">
            <div className="plan-list-stage">
              {stage.label}
              <span className="plan-column-count">{stageTasks.length}</span>
            </div>
            {stageTasks.map((task) => {
              const meta = CATEGORY_META[task.category];
              const progress = taskProgress(task);
              const done = task.subtasks.filter((item) => item.done).length;
              return (
                <button key={task.id} className="plan-row" onClick={() => onOpen(task)}>
                  <span className="plan-row-dot" style={{ background: meta.color }} />
                  <span className="plan-row-title">{task.title}</span>
                  <span className="plan-row-tag" style={{ background: meta.soft, color: meta.color }}>
                    {meta.label}
                  </span>
                  {task.subtasks.length > 0 && (
                    <span className="plan-row-sub">
                      {done}/{task.subtasks.length}
                    </span>
                  )}
                  {task.deadline && <span className="plan-row-deadline">{task.deadline}</span>}
                  <span className="plan-row-progress">
                    <span className="plan-card-bar" style={{ background: meta.color, width: `${progress}%` }} />
                  </span>
                  {task.assignee && <span className="plan-card-avatar">{task.assignee.slice(0, 2)}</span>}
                </button>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
