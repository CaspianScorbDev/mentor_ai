import { useState } from "react";
import { Check, Plus, Trash2, X } from "lucide-react";
import type { GoalDto } from "../../api";
import type { EventCategory } from "../calendar/types";
import { CATEGORY_META, CATEGORY_ORDER } from "../calendar/utils";
import type { PlanStage, PlanTask, Subtask } from "./types";
import { STAGES } from "./data";

export interface TaskChanges {
  title: string;
  stage: PlanStage;
  category: EventCategory;
  projectId?: number;
  deadline?: string;
  assignee?: string;
}

interface TaskModalProps {
  task: PlanTask;
  projects: GoalDto[];
  onClose: () => void;
  onSave: (changes: TaskChanges) => void;
  onDelete: (id: number) => void;
  onAddSubtask: (title: string) => void;
  onToggleSubtask: (subtask: Subtask) => void;
}

export function TaskModal({
  task,
  projects,
  onClose,
  onSave,
  onDelete,
  onAddSubtask,
  onToggleSubtask,
}: TaskModalProps) {
  const [title, setTitle] = useState(task.title);
  const [stage, setStage] = useState<PlanStage>(task.stage);
  const [category, setCategory] = useState<EventCategory>(task.category);
  const [projectId, setProjectId] = useState<number | undefined>(task.projectId);
  const [deadline, setDeadline] = useState(task.deadline ?? "");
  const [assignee, setAssignee] = useState(task.assignee ?? "");
  const [subtask, setSubtask] = useState("");

  const save = () => {
    onSave({
      title: title.trim() || task.title,
      stage,
      category,
      projectId,
      deadline: deadline.trim() || undefined,
      assignee: assignee.trim() || undefined,
    });
    onClose();
  };

  const addSub = () => {
    const value = subtask.trim();
    if (!value) return;
    onAddSubtask(value);
    setSubtask("");
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span className="modal-title">Задача</span>
          <button className="icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <input
          className="field-input task-title-input"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        {projects.length > 0 && (
          <label className="field">
            <span className="field-label">Мини-проект</span>
            <select
              className="field-input"
              value={projectId ?? ""}
              onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : undefined)}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.title}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="field-row">
          <label className="field">
            <span className="field-label">Этап</span>
            <select
              className="field-input"
              value={stage}
              onChange={(e) => setStage(e.target.value as PlanStage)}
            >
              {STAGES.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Исполнитель</span>
            <input
              className="field-input"
              value={assignee}
              placeholder="Имя или инициалы"
              onChange={(e) => setAssignee(e.target.value)}
            />
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span className="field-label">Дедлайн</span>
            <input
              className="field-input"
              value={deadline}
              placeholder="Например, 5 дней"
              onChange={(e) => setDeadline(e.target.value)}
            />
          </label>
          <div className="field">
            <span className="field-label">Категория</span>
            <div className="cat-picker">
              {CATEGORY_ORDER.map((id) => {
                const meta = CATEGORY_META[id];
                return (
                  <button
                    key={id}
                    className={`cat-option${category === id ? " active" : ""}`}
                    style={
                      category === id
                        ? { background: meta.soft, color: meta.color, borderColor: meta.color }
                        : undefined
                    }
                    onClick={() => setCategory(id)}
                  >
                    <span className="cat-dot" style={{ background: meta.color }} />
                    {meta.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="field">
          <span className="field-label">Подзадачи</span>
          <div className="subtask-list">
            {task.subtasks.map((item) => (
              <label key={item.id} className="subtask">
                <button
                  className={`subtask-check${item.done ? " done" : ""}`}
                  onClick={() => onToggleSubtask(item)}
                >
                  {item.done && <Check size={12} />}
                </button>
                <span className={item.done ? "subtask-done" : ""}>{item.title}</span>
              </label>
            ))}
            <div className="subtask-add">
              <input
                className="field-input"
                value={subtask}
                placeholder="Добавить подзадачу"
                onChange={(e) => setSubtask(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addSub()}
              />
              <button className="icon-btn" onClick={addSub}>
                <Plus size={16} />
              </button>
            </div>
          </div>
        </div>

        <div className="modal-actions">
          <button className="ghost-btn danger" onClick={() => onDelete(task.id)}>
            <Trash2 size={15} />
            Удалить
          </button>
          <button className="primary-btn" onClick={save}>
            Сохранить
          </button>
        </div>
      </div>
    </div>
  );
}
