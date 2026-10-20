import { useCallback, useEffect, useState } from "react";
import { Check, Cpu, RefreshCw, Save, Sparkles } from "lucide-react";
import { api, type AiConfigDto, type AiConfigInput } from "../api";

const PROVIDER_OPTIONS = [
  { value: "", label: "По умолчанию (из конфига)" },
  { value: "ollama", label: "Ollama — локально" },
  { value: "groq", label: "Groq — облако" },
];

function toNumberOrNull(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

export function AiSettings() {
  const [config, setConfig] = useState<AiConfigDto | null>(null);
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState("");
  const [maxTokens, setMaxTokens] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");

  const [models, setModels] = useState<string[]>([]);
  const [modelError, setModelError] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyConfig = useCallback((data: AiConfigDto) => {
    setConfig(data);
    setProvider(data.provider ?? "");
    setModel(data.model ?? "");
    setTemperature(data.temperature == null ? "" : String(data.temperature));
    setMaxTokens(data.max_tokens == null ? "" : String(data.max_tokens));
    setSystemPrompt(data.system_prompt ?? "");
  }, []);

  const loadModels = useCallback(async (target: string) => {
    setLoadingModels(true);
    setModelError(null);
    try {
      const result = await api.listAiModels(target);
      setModels(result.models.map((item) => item.model));
      if (result.error) setModelError(result.error);
    } catch (err) {
      setModels([]);
      setModelError((err as Error).message);
    } finally {
      setLoadingModels(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    api
      .getAiConfig()
      .then((data) => {
        if (alive) applyConfig(data);
      })
      .catch((err: Error) => {
        if (alive) setError(err.message);
      });
    return () => {
      alive = false;
    };
  }, [applyConfig]);

  const activeProvider = provider || config?.effective_provider || "ollama";

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- refresh model list for the selected provider
    void loadModels(activeProvider);
  }, [activeProvider, loadModels]);

  useEffect(() => {
    if (!saved && !error) return;
    const id = setTimeout(() => {
      setSaved(false);
      setError(null);
    }, 3000);
    return () => clearTimeout(id);
  }, [saved, error]);

  const changes: AiConfigInput = {};
  if (config) {
    if ((config.provider ?? "") !== provider) changes.provider = provider || null;
    if ((config.model ?? "") !== model.trim()) changes.model = model.trim() || null;
    if ((config.temperature == null ? "" : String(config.temperature)) !== temperature.trim()) {
      changes.temperature = toNumberOrNull(temperature);
    }
    if ((config.max_tokens == null ? "" : String(config.max_tokens)) !== maxTokens.trim()) {
      changes.max_tokens = toNumberOrNull(maxTokens);
    }
    if ((config.system_prompt ?? "") !== systemPrompt.trim()) {
      changes.system_prompt = systemPrompt.trim() || null;
    }
  }
  const dirty = Object.keys(changes).length > 0;

  const save = async () => {
    if (!config || !dirty) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateAiConfig(changes);
      applyConfig(updated);
      setSaved(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="settings-card">
      <div className="settings-card-head">
        <span className="settings-card-icon">
          <Cpu size={18} />
        </span>
        <div className="settings-card-titles">
          <span className="settings-card-title">Модель ИИ</span>
          <span className="settings-card-sub">
            Все поля необязательны — пустые берут значения из конфигурации сервера
          </span>
        </div>
        <button
          className="icon-btn"
          title="Обновить список моделей"
          onClick={() => void loadModels(activeProvider)}
          disabled={loadingModels}
        >
          <RefreshCw size={16} className={loadingModels ? "spin" : undefined} />
        </button>
      </div>

      <div className="field-row">
        <label className="field">
          <span className="field-label">Провайдер</span>
          <select
            className="field-input"
            value={provider}
            onChange={(event) => setProvider(event.target.value)}
          >
            {PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Модель</span>
          <input
            className="field-input"
            list="ai-model-options"
            value={model}
            placeholder={config?.effective_model ?? "qwen3:8b"}
            onChange={(event) => setModel(event.target.value)}
          />
          <datalist id="ai-model-options">
            {models.map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
        </label>
      </div>

      {modelError && <p className="settings-hint">{modelError}</p>}

      <div className="field-row">
        <label className="field">
          <span className="field-label">Температура</span>
          <input
            className="field-input"
            type="number"
            min="0"
            max="2"
            step="0.1"
            value={temperature}
            placeholder={config ? String(config.effective_temperature) : "0.7"}
            onChange={(event) => setTemperature(event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field-label">Лимит ответа (токены)</span>
          <input
            className="field-input"
            type="number"
            min="1"
            max="32768"
            step="1"
            value={maxTokens}
            placeholder={config ? String(config.effective_max_tokens) : "1024"}
            onChange={(event) => setMaxTokens(event.target.value)}
          />
        </label>
      </div>

      <label className="field">
        <span className="field-label">Дополнительная инструкция (system prompt)</span>
        <textarea
          className="field-input"
          rows={3}
          value={systemPrompt}
          placeholder="Например: отвечай кратко, давай конкретные шаги и дедлайны"
          onChange={(event) => setSystemPrompt(event.target.value)}
        />
      </label>

      <div className="ai-config-effective">
        <Sparkles size={14} />
        Сейчас используется: {config?.effective_provider ?? "—"} · {config?.effective_model ?? "—"}
      </div>

      <div className="settings-save">
        <button className="primary-btn" onClick={() => void save()} disabled={saving || !dirty}>
          {saved ? <Check size={16} /> : <Save size={16} />}
          {saving ? "Сохранение…" : saved ? "Сохранено" : "Сохранить модель"}
        </button>
        {dirty && !saving && <span className="settings-hint">Есть несохранённые изменения</span>}
      </div>
    </div>
  );
}
