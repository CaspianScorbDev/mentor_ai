import { useMemo, useRef, useState } from "react";
import { Check, Maximize2, Minus, Plus, Sparkles } from "lucide-react";
import type { GoalDto } from "../../api";
import { CATEGORY_META } from "../calendar/utils";
import type { EventCategory } from "../calendar/types";
import type { MapLink, MapNode, PlanTask } from "./types";

const CANVAS_W = 1200;
const CANVAS_H = 800;

const CATEGORY_LABELS: Record<EventCategory, string> = {
  work: "Работа",
  personal: "Личное",
  aida: "Aida",
};

const CATEGORY_ORDER: EventCategory[] = ["work", "personal", "aida"];

function buildGraph(goal: GoalDto | null, tasks: PlanTask[]): {
  nodes: MapNode[];
  links: MapLink[];
} {
  const present = CATEGORY_ORDER.filter((category) =>
    tasks.some((task) => task.category === category),
  );
  const categories = present.length > 0 ? present : CATEGORY_ORDER;

  const nodes: MapNode[] = [];
  const links: MapLink[] = [];

  const dirY = 120;
  const taskStartY = 270;
  const taskGap = 82;
  const left = 150;
  const right = CANVAS_W - 150;
  const step = categories.length > 1 ? (right - left) / (categories.length - 1) : 0;

  nodes.push({
    id: "goal",
    label: goal?.title ?? "Главная цель",
    x: CANVAS_W / 2,
    y: 660,
    kind: "goal",
  });

  categories.forEach((category, index) => {
    const x = categories.length > 1 ? left + step * index : CANVAS_W / 2;
    const dirId = `dir-${category}`;
    nodes.push({
      id: dirId,
      label: CATEGORY_LABELS[category],
      x,
      y: dirY,
      kind: "direction",
      category,
    });
    links.push({ from: "goal", to: dirId });

    const categoryTasks = tasks.filter((task) => task.category === category);
    categoryTasks.forEach((task, taskIndex) => {
      const taskId = `task-${task.id}`;
      nodes.push({
        id: taskId,
        label: task.title,
        x,
        y: taskStartY + taskIndex * taskGap,
        kind: "task",
        category,
        done: task.stage === "done",
      });
      links.push({ from: dirId, to: taskId });
    });
  });

  return { nodes, links };
}

function buildRecommendation(tasks: PlanTask[]): string {
  const review = tasks.filter((task) => task.stage === "review");
  if (review.length > 0) {
    return `«${review[0].title}» ждёт проверки — прогоните её сегодня, чтобы не блокировать цель.`;
  }
  const active = tasks.filter((task) => task.stage !== "done");
  if (active.length > 0) {
    return `В работе ${active.length} задач. Следующий шаг — «${active[0].title}».`;
  }
  if (tasks.length > 0) {
    return "Все задачи выполнены — самое время поставить следующую веху.";
  }
  return "Добавьте первую задачу, и она появится на карте связей.";
}

interface MapViewProps {
  goal: GoalDto | null;
  tasks: PlanTask[];
  onAddTask: (title: string) => void;
}

export function MapView({ goal, tasks, onAddTask }: MapViewProps) {
  const [zoom, setZoom] = useState(0.9);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [full, setFull] = useState(false);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);

  const { nodes, links } = useMemo(() => buildGraph(goal, tasks), [goal, tasks]);
  const recommendation = useMemo(() => buildRecommendation(tasks), [tasks]);
  const nodeById = (id: string) => nodes.find((node) => node.id === id);

  const onPointerDown = (event: React.PointerEvent) => {
    if ((event.target as HTMLElement).closest(".map-node")) return;
    drag.current = { x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent) => {
    if (!drag.current) return;
    setPan({
      x: drag.current.panX + (event.clientX - drag.current.x),
      y: drag.current.panY + (event.clientY - drag.current.y),
    });
  };

  const onPointerUp = () => {
    drag.current = null;
  };

  const addNode = () => {
    const title = window.prompt("Название задачи", "Новая задача");
    if (title && title.trim()) onAddTask(title.trim());
  };

  return (
    <div className={`map-view${full ? " fullscreen" : ""}`}>
      <div
        className="map-viewport"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        <div
          className="map-canvas"
          style={{
            width: CANVAS_W,
            height: CANVAS_H,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          }}
        >
          <svg className="map-links" width={CANVAS_W} height={CANVAS_H}>
            {links.map((link) => {
              const from = nodeById(link.from);
              const to = nodeById(link.to);
              if (!from || !to) return null;
              return (
                <line
                  key={`${link.from}-${link.to}`}
                  x1={from.x}
                  y1={from.y}
                  x2={to.x}
                  y2={to.y}
                  className="map-link"
                />
              );
            })}
          </svg>

          {nodes.map((node) => {
            const meta = node.category ? CATEGORY_META[node.category] : null;
            return (
              <div
                key={node.id}
                className={`map-node ${node.kind}${node.done ? " done" : ""}`}
                style={{
                  left: node.x,
                  top: node.y,
                  borderColor: meta?.color,
                  background: node.kind === "task" && meta ? meta.soft : undefined,
                  color: node.kind === "task" && meta ? meta.color : undefined,
                }}
              >
                {node.done && (
                  <span className="map-node-check">
                    <Check size={11} />
                  </span>
                )}
                {node.label}
              </div>
            );
          })}
        </div>

        <div className="map-controls">
          <button className="icon-btn" onClick={() => setZoom((z) => Math.min(1.8, z + 0.1))}>
            <Plus size={16} />
          </button>
          <button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.4, z - 0.1))}>
            <Minus size={16} />
          </button>
          <button
            className="icon-btn"
            onClick={() => {
              setZoom(0.9);
              setPan({ x: 0, y: 0 });
            }}
          >
            <span className="map-reset">100%</span>
          </button>
          <button className="icon-btn" onClick={() => setFull((v) => !v)}>
            <Maximize2 size={16} />
          </button>
          <button className="icon-btn" title="Добавить задачу" onClick={addNode}>
            <Plus size={16} />
          </button>
        </div>

        <div className="map-hint">Перетаскивайте, чтобы сместить · колесо для масштаба</div>
      </div>

      <div className="map-recommendation">
        <span className="rec-icon">
          <Sparkles size={14} />
        </span>
        <div>
          <div className="rec-title">Рекомендация Aida</div>
          <p className="rec-text">{recommendation}</p>
        </div>
      </div>
    </div>
  );
}
