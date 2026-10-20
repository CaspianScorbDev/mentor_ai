import { useState } from "react";
import { CalendarClock, Plus } from "lucide-react";
import { CATEGORY_META } from "../calendar/utils";
import type { PlanStage, PlanTask } from "./types";
import { STAGES } from "./data";
import { taskProgress } from "./progress";

interface BoardProps {
  tasks: PlanTask[];
  onOpen: (task: PlanTask) => void;
  onAdd: (stage: PlanStage, title: string) => void;
}
function BoardCard({ task, onOpen }: { task: PlanTask; onOpen: (task: PlanTask) => void }) {
  const meta = CATEGORY_META[task.category];
  const progress = taskProgress(task);
  const done = task.subtasks.filter((item) => item.done).length;

  return (
    <button className="plan-card" onClick={() => onOpen(task)}>
      <span className="plan-card-cat" style={{ color: meta.color }}>
        <span className="cat-dot" style={{ background: meta.color }} />
        {meta.label}
      </span>
      <span className="plan-card-title">{task.title}</span>

      {task.subtasks.length > 0 && (
        <>
          <span className="plan-card-progress">
            <span className="plan-card-bar" style={{ background: meta.color, width: `${progress}%` }} />
          </span>
          <span className="plan-card-subcount">
            {done}/{task.subtasks.length} подзадач
          </span>
        </>
      )}

      <span className="plan-card-meta">
        {task.deadline && (
          <span className="plan-card-chip">
            <CalendarClock size={12} />
            {task.deadline}
          </span>
        )}
        {task.assignee && (
          <span className="plan-card-avatar" title={task.assignee}>
            {task.assignee.slice(0, 2)}
          </span>
        )}
      </span>
    </button>
  );
}

export function Board({ tasks, onOpen, onAdd }: BoardProps) {
  const [adding, setAdding] = useState<PlanStage | null>(null);
  const [title, setTitle] = useState("");

  const submit = (stage: PlanStage) => {
    const trimmed = title.trim();
    if (trimmed) onAdd(stage, trimmed);
    setTitle("");
    setAdding(null);
  };

  return (
    <div className="plan-board">
      {STAGES.map((stage) => {
        const stageTasks = tasks.filter((task) => task.stage === stage.id);
        return (
          <div key={stage.id} className="plan-column">
            <div className="plan-column-head">
              <span className="plan-column-title">{stage.label}</span>
              <span className="plan-column-count">{stageTasks.length}</span>
            </div>
            <div className="plan-column-body">
              {stageTasks.map((task) => (
                <BoardCard key={task.id} task={task} onOpen={onOpen} />
              ))}
              {adding === stage.id ? (
                <div className="plan-add">
                  <input
                    className="field-input"
                    autoFocus
                    value={title}
                    placeholder="Название задачи"
                    onChange={(e) => setTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") submit(stage.id);
                      if (e.key === "Escape") setAdding(null);
                    }}
                  />
                  <div className="plan-add-actions">
                    <button className="primary-btn sm" onClick={() => submit(stage.id)}>
                      Добавить
                    </button>
                    <button className="ghost-btn sm" onClick={() => setAdding(null)}>
                      Отмена
                    </button>
                  </div>
                </div>
              ) : (
                <button className="plan-add-btn" onClick={() => setAdding(stage.id)}>
                  <Plus size={15} />
                  Добавить задачу
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
