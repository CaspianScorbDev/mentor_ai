import { useEffect, useMemo, useState } from "react";
import { Brain, Check, Moon, Save, SlidersHorizontal, UserRound } from "lucide-react";
import { api, type ContextDto, type ContextInput } from "../api";
import { AiSettings } from "./AiSettings";

interface SettingsProps {
  context: ContextDto | null;
  userName: string;
  theme: "light" | "dark";
  onContextChange: (context: ContextDto) => void;
  onToggleTheme: () => void;
}

const LANGUAGE_OPTIONS = ["Русский", "English", "Deutsch", "Español"];

const SPECIALIZATION_OPTIONS = [
  "Продуктовый менеджмент",
  "Карьера и рост",
  "Продуктивность",
  "Инженерия и код",
  "Учёба и экзамены",
  "Финансы",
];

const STYLE_OPTIONS = ["Кратко и по делу", "Подробно с примерами", "Дружелюбно и поддерживающе"];
const TONE_OPTIONS = ["Поддерживающий", "Требовательный", "Наставник-стратег", "Мягкий коуч"];

const CONFIGURABLE: (keyof ContextDto)[] = [
  "user_name",
  "current_goal",
  "specialization",
  "communication_style",
  "mentor_tone",
  "interests",
  "language",
  "mentor_mode",
  "use_schedule",
  "use_plans",
];

function Switch({
  on,
  disabled,
  onToggle,
}: {
  on: boolean;
  disabled?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      className={`switch${on ? " on" : ""}`}
      onClick={onToggle}
      disabled={disabled}
      aria-pressed={on}
    >
      <span className="switch-knob" />
    </button>
  );
}

export function Settings({ context, userName, theme, onContextChange, onToggleTheme }: SettingsProps) {
  const [form, setForm] = useState<ContextDto | null>(context);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- follow the loaded context
    setForm(context);
  }, [context]);

  useEffect(() => {
    if (!saved && !error) return;
    const id = setTimeout(() => {
      setSaved(false);
      setError(null);
    }, 3000);
    return () => clearTimeout(id);
  }, [saved, error]);

  const dirty = useMemo(() => {
    if (!context || !form) return false;
    return CONFIGURABLE.some((field) => context[field] !== form[field]);
  }, [context, form]);

  if (!form) {
    return (
      <div className="integrations">
        <div className="integrations-head">
          <h2 className="section-heading">Ещё</h2>
          <p className="section-text">Загрузка настроек…</p>
        </div>
      </div>
    );
  }

  const update = <K extends keyof ContextDto>(key: K, value: ContextDto[K]) =>
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const save = async () => {
    if (!form || !context) return;
    const changes: ContextInput = {};
    for (const field of CONFIGURABLE) {
      if (context[field] !== form[field]) {
        (changes as Record<string, unknown>)[field] = form[field];
      }
    }
    if (Object.keys(changes).length === 0) return;

    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateContext(changes);
      onContextChange(updated);
      setForm(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="integrations">
      <div className="integrations-head">
        <h2 className="section-heading">Ещё</h2>
        <p className="section-text">
          Настройте профиль, контекст ИИ и поведение наставника — Aida сразу учтёт это в ответах.
        </p>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <UserRound size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Профиль</span>
            <span className="settings-card-sub">Как к вам обращаться и на каком языке отвечать</span>
          </div>
          {form.configured && (
            <span className="context-pill">
              <span className="context-dot" />
              Контекст настроен
            </span>
          )}
        </div>
        <div className="field-row">
          <label className="field">
            <span className="field-label">Имя</span>
            <input
              className="field-input"
              value={form.user_name}
              placeholder={userName}
              onChange={(e) => update("user_name", e.target.value)}
            />
          </label>
          <label className="field">
            <span className="field-label">Язык ответов</span>
            <select
              className="field-input"
              value={form.language}
              onChange={(e) => update("language", e.target.value)}
            >
              {LANGUAGE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Brain size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Контекст ИИ</span>
            <span className="settings-card-sub">
              Цели, специализация и стиль — попадут в системный промпт
            </span>
          </div>
        </div>

        <label className="field">
          <span className="field-label">Текущая цель</span>
          <textarea
            className="field-input"
            rows={2}
            value={form.current_goal}
            placeholder="Например: запустить продукт к концу квартала"
            onChange={(e) => update("current_goal", e.target.value)}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span className="field-label">Специализация наставника</span>
            <input
              className="field-input"
              list="specialization-options"
              value={form.specialization}
              placeholder="Продуктивность"
              onChange={(e) => update("specialization", e.target.value)}
            />
            <datalist id="specialization-options">
              {SPECIALIZATION_OPTIONS.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </label>
          <label className="field">
            <span className="field-label">Формат общения</span>
            <input
              className="field-input"
              list="style-options"
              value={form.communication_style}
              placeholder="Кратко и по делу"
              onChange={(e) => update("communication_style", e.target.value)}
            />
            <datalist id="style-options">
              {STYLE_OPTIONS.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </label>
        </div>

        <div className="field-row">
          <label className="field">
            <span className="field-label">Тон наставника</span>
            <input
              className="field-input"
              list="tone-options"
              value={form.mentor_tone}
              placeholder="Поддерживающий"
              onChange={(e) => update("mentor_tone", e.target.value)}
            />
            <datalist id="tone-options">
              {TONE_OPTIONS.map((option) => (
                <option key={option} value={option} />
              ))}
            </datalist>
          </label>
          <label className="field">
            <span className="field-label">Что учитывать</span>
            <input
              className="field-input"
              value={form.interests}
              placeholder="Спорт, чтение, английский"
              onChange={(e) => update("interests", e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <SlidersHorizontal size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Поведение наставника</span>
            <span className="settings-card-sub">Насколько активно Aida вовлекается в работу</span>
          </div>
        </div>

        <div className="settings-toggle-row">
          <div className="settings-toggle-text">
            <span className="settings-card-title">Режим наставника</span>
            <span className="settings-card-sub">Конкретные шаги и контроль прогресса</span>
          </div>
          <Switch on={form.mentor_mode} onToggle={() => update("mentor_mode", !form.mentor_mode)} />
        </div>

        <div className="settings-toggle-row">
          <div className="settings-toggle-text">
            <span className="settings-card-title">Учитывать расписание</span>
            <span className="settings-card-sub">Ссылаться на события дня в ответах</span>
          </div>
          <Switch
            on={form.use_schedule}
            onToggle={() => update("use_schedule", !form.use_schedule)}
          />
        </div>

        <div className="settings-toggle-row">
          <div className="settings-toggle-text">
            <span className="settings-card-title">Учитывать планы</span>
            <span className="settings-card-sub">Помогать с целями и задачами</span>
          </div>
          <Switch on={form.use_plans} onToggle={() => update("use_plans", !form.use_plans)} />
        </div>
      </div>

      <AiSettings />

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Moon size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Оформление</span>
            <span className="settings-card-sub">Тёмная тема интерфейса</span>
          </div>
        </div>
        <div className="settings-toggle-row">
          <div className="settings-toggle-text">
            <span className="settings-card-title">Тёмный фон</span>
            <span className="settings-card-sub">Комфортно для глаз в любое время суток</span>
          </div>
          <Switch on={theme === "dark"} onToggle={onToggleTheme} />
        </div>
      </div>

      <div className="settings-save">
        <button className="primary-btn" onClick={() => void save()} disabled={saving || !dirty}>
          {saved ? <Check size={16} /> : <Save size={16} />}
          {saving ? "Сохранение…" : saved ? "Сохранено" : "Сохранить"}
        </button>
        {dirty && !saving && <span className="settings-hint">Есть несохранённые изменения</span>}
      </div>

      {error && <div className="toast">{error}</div>}
    </div>
  );
}
