import { useEffect, useMemo, useState } from "react";
import {
  CalendarClock,
  FolderKanban,
  Gauge,
  Kanban,
  List,
  Map as MapIcon,
  Plus,
  Target,
  Trash2,
} from "lucide-react";
import { api, type GoalDto, type TaskDto } from "../../api";
import type { PlanMode, PlanStage, PlanTask } from "./types";
import { goalProgress, pace } from "./progress";
import { Board } from "./Board";
import { ListView } from "./ListView";
import { MapView } from "./MapView";
import { TaskModal, type TaskChanges } from "./TaskModal";

const MODES: { id: PlanMode; label: string; icon: typeof List }[] = [
  { id: "board", label: "Доска", icon: Kanban },
  { id: "map", label: "Карта", icon: MapIcon },
  { id: "list", label: "Список", icon: List },
];

function mapTask(dto: TaskDto): PlanTask {
  return {
    id: dto.id,
    title: dto.title,
    stage: dto.stage,
    category: dto.category,
    projectId: dto.goal_id ?? undefined,
    deadline: dto.deadline ?? undefined,
    assignee: dto.assignee ?? undefined,
    subtasks: dto.subtasks.map((item) => ({
      id: item.id,
      title: item.title,
      done: item.done,
    })),
  };
}

function daysUntil(deadline: string | null): number {
  if (!deadline) return 30;
  const end = new Date(`${deadline}T00:00:00`);
  const diff = Math.ceil((end.getTime() - Date.now()) / 86_400_000);
  return Math.max(diff, 0);
}

function GoalRing({ value }: { value: number }) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - value / 100);
  return (
    <svg className="goal-ring" width={76} height={76} viewBox="0 0 76 76">
      <circle cx={38} cy={38} r={radius} className="goal-ring-track" />
      <circle
        cx={38}
        cy={38}
        r={radius}
        className="goal-ring-value"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 38 38)"
      />
      <text x={38} y={43} textAnchor="middle" className="goal-ring-text">
        {value}%
      </text>
    </svg>
  );
}

export function Plans() {
  const [projects, setProjects] = useState<GoalDto[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<PlanTask[]>([]);
  const [mode, setMode] = useState<PlanMode>("board");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showGoal, setShowGoal] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    Promise.all([api.listProjects(), api.listTasks()])
      .then(([projectDtos, taskDtos]) => {
        if (!alive) return;
        setProjects(projectDtos);
        setActiveId((prev) => prev ?? projectDtos[0]?.id ?? null);
        setTasks(taskDtos.map(mapTask));
      })
      .catch((err: unknown) => {
        if (alive) setError((err as Error).message);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!error) return;
    const id = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(id);
  }, [error]);

  const activeProject = projects.find((project) => project.id === activeId) ?? null;
  const projectTasks = useMemo(
    () => tasks.filter((task) => task.projectId === activeId),
    [tasks, activeId],
  );

  const progress = useMemo(() => goalProgress(projectTasks), [projectTasks]);
  const daysLeft = activeProject ? daysUntil(activeProject.deadline) : 30;
  const paceLabel = pace(progress, daysLeft);
  const doneCount = projectTasks.filter((task) => task.stage === "done").length;
  const selected = tasks.find((task) => task.id === selectedId) ?? null;

  const replaceTask = (updated: PlanTask) =>
    setTasks((prev) => prev.map((task) => (task.id === updated.id ? updated : task)));

  const saveTask = async (id: number, changes: TaskChanges) => {
    try {
      const dto = await api.updateTask(id, {
        title: changes.title,
        stage: changes.stage,
        category: changes.category,
        goal_id: changes.projectId ?? null,
        deadline: changes.deadline ?? null,
        assignee: changes.assignee ?? null,
      });
      replaceTask(mapTask(dto));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const deleteTask = async (id: number) => {
    try {
      await api.deleteTask(id);
      setTasks((prev) => prev.filter((task) => task.id !== id));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSelectedId(null);
    }
  };

  const addTask = async (stage: PlanStage, title: string) => {
    try {
      const dto = await api.createTask({
        title,
        stage,
        category: "work",
        goal_id: activeId,
      });
      setTasks((prev) => [mapTask(dto), ...prev]);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const addSubtask = async (taskId: number, title: string) => {
    try {
      const dto = await api.addSubtask(taskId, title);
      replaceTask(mapTask(dto));
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const toggleSubtask = async (taskId: number, subtaskId: number, done: boolean) => {
    try {
      const dto = await api.updateSubtask(subtaskId, { done });
      setTasks((prev) =>
        prev.map((task) =>
          task.id === taskId
            ? {
                ...task,
                subtasks: task.subtasks.map((item) =>
                  item.id === dto.id ? { id: dto.id, title: dto.title, done: dto.done } : item,
                ),
              }
            : task,
        ),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const createProject = async (title: string) => {
    try {
      const dto = await api.createProject({ title });
      setProjects((prev) => [...prev, dto]);
      setActiveId(dto.id);
      setShowCreate(false);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const deleteProject = async (project: GoalDto) => {
    if (!window.confirm(`Удалить проект «${project.title}» и все его задачи?`)) return;
    try {
      await api.deleteProject(project.id);
      setProjects((prev) => prev.filter((item) => item.id !== project.id));
      setTasks((prev) => prev.filter((task) => task.projectId !== project.id));
      setActiveId((prev) => {
        if (prev !== project.id) return prev;
        return projects.find((item) => item.id !== project.id)?.id ?? null;
      });
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="plans">
      <div className="projects-bar">
        <div className="projects-scroll">
          {projects.map((project) => (
            <button
              key={project.id}
              className={`project-chip${project.id === activeId ? " active" : ""}`}
              onClick={() => {
                setActiveId(project.id);
                setShowGoal(false);
              }}
            >
              <FolderKanban size={14} />
              <span className="project-chip-title">{project.title}</span>
            </button>
          ))}
          <button className="project-chip add" onClick={() => setShowCreate((v) => !v)}>
            <Plus size={14} />
            Проект
          </button>
        </div>
      </div>

      {showCreate && (
        <CreateProjectForm
          onCancel={() => setShowCreate(false)}
          onSubmit={(title) => void createProject(title)}
        />
      )}

      <div className="plan-goal">
        <div className="plan-goal-main">
          <span className="plan-goal-kicker">
            <Target size={14} />
            Мини-проект
          </span>
          <h2 className="plan-goal-title">{activeProject?.title ?? "Выберите проект"}</h2>
          <p className="plan-goal-desc">{activeProject?.description ?? ""}</p>
          <div className="plan-goal-actions">
            {activeProject && (
              <>
                <button className="ghost-btn sm" onClick={() => setShowGoal((v) => !v)}>
                  {showGoal ? "Скрыть детали" : "К деталям проекта"}
                </button>
                <button
                  className="ghost-btn sm danger"
                  onClick={() => void deleteProject(activeProject)}
                >
                  <Trash2 size={14} />
                  Удалить
                </button>
              </>
            )}
          </div>
          {showGoal && activeProject && (
            <div className="goal-details">
              <span>
                Задач завершено: {doneCount} из {projectTasks.length}
              </span>
              <span>Средний темп: {paceLabel}</span>
              <span>Дедлайн: через {daysLeft} дн.</span>
            </div>
          )}
        </div>

        <div className="plan-goal-stats">
          <GoalRing value={progress} />
          <div className="goal-stat">
            <span className="goal-stat-label">
              <CalendarClock size={14} /> До дедлайна
            </span>
            <span className="goal-stat-value">{daysLeft} дн.</span>
          </div>
          <div className="goal-stat">
            <span className="goal-stat-label">
              <Gauge size={14} /> Темп
            </span>
            <span className="goal-stat-value">{paceLabel}</span>
          </div>
        </div>
      </div>

      <div className="plan-toolbar">
        <div className="mode-switch">
          {MODES.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={`mode-tab${mode === item.id ? " active" : ""}`}
                onClick={() => setMode(item.id)}
              >
                <Icon size={15} />
                {item.label}
              </button>
            );
          })}
        </div>
        <button className="primary-btn" onClick={() => setMode("board")}>
          <Plus size={16} />
          Задача
        </button>
      </div>

      <div className="plan-content">
        {mode === "board" && (
          <Board
            tasks={projectTasks}
            onOpen={(task) => setSelectedId(task.id)}
            onAdd={addTask}
          />
        )}
        {mode === "list" && (
          <ListView tasks={projectTasks} onOpen={(task) => setSelectedId(task.id)} />
        )}
        {mode === "map" && (
          <MapView
            goal={activeProject}
            tasks={projectTasks}
            onAddTask={(title) => void addTask("ideas", title)}
          />
        )}
      </div>

      {selected && (
        <TaskModal
          task={selected}
          projects={projects}
          onClose={() => setSelectedId(null)}
          onSave={(changes) => void saveTask(selected.id, changes)}
          onDelete={(id) => void deleteTask(id)}
          onAddSubtask={(title) => void addSubtask(selected.id, title)}
          onToggleSubtask={(subtask) => void toggleSubtask(selected.id, subtask.id, !subtask.done)}
        />
      )}

      {error && <div className="toast">{error}</div>}
    </div>
  );
}

function CreateProjectForm({
  onCancel,
  onSubmit,
}: {
  onCancel: () => void;
  onSubmit: (title: string) => void;
}) {
  const [title, setTitle] = useState("");
  const submit = () => {
    const trimmed = title.trim();
    if (trimmed) onSubmit(trimmed);
  };
  return (
    <div className="project-create">
      <input
        className="field-input"
        autoFocus
        value={title}
        placeholder="Название мини-проекта"
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") submit();
          if (e.key === "Escape") onCancel();
        }}
      />
      <div className="project-create-actions">
        <button className="primary-btn sm" onClick={submit}>
          Создать
        </button>
        <button className="ghost-btn sm" onClick={onCancel}>
          Отмена
        </button>
      </div>
    </div>
  );
}
