import { useEffect, useState } from "react";
import { Bell, Mail, Play, Send, Timer } from "lucide-react";
import { api, type SettingsDto } from "../api";
import { pomodoro } from "../pomodoro";

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

function StatusNote({ ok, onLabel, offLabel }: { ok: boolean; onLabel: string; offLabel: string }) {
  return <span className={`integration-sub${ok ? " ok" : ""}`}>{ok ? onLabel : offLabel}</span>;
}

export function Integrations() {
  const [settings, setSettings] = useState<SettingsDto | null>(null);
  const [fields, setFields] = useState({
    telegram_chat_id: "",
    email_address: "",
    digest_time: "09:00",
    pomodoro_minute: 25,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission>(() =>
    typeof Notification !== "undefined" ? Notification.permission : "default",
  );

  useEffect(() => {
    let alive = true;
    api
      .getSettings()
      .then((data) => {
        if (!alive) return;
        setSettings(data);
        setFields({
          telegram_chat_id: data.telegram_chat_id ?? "",
          email_address: data.email_address ?? "",
          digest_time: data.digest_time,
          pomodoro_minute: data.pomodoro_minute,
        });
      })
      .catch((err: unknown) => {
        if (alive) setError((err as Error).message);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!status && !error) return;
    const id = setTimeout(() => {
      setStatus(null);
      setError(null);
    }, 5000);
    return () => clearTimeout(id);
  }, [status, error]);

  const patch = async (changes: Partial<SettingsDto>) => {
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateSettings(changes);
      setSettings(updated);
      return updated;
    } catch (err) {
      setError((err as Error).message);
      return null;
    } finally {
      setSaving(false);
    }
  };

  const runAction = async (action: () => Promise<{ detail?: string; ok?: boolean }>) => {
    setError(null);
    setStatus("Выполняется…");
    try {
      const result = await action();
      if (result.ok === false && result.detail) {
        setStatus(null);
        setError(result.detail);
        return;
      }
      setStatus(result.detail ?? "Готово");
    } catch (err) {
      setStatus(null);
      setError((err as Error).message);
    }
  };

  const enableDeviceNotifications = async () => {
    if (typeof Notification === "undefined") {
      setError("Уведомления не поддерживаются этим браузером");
      return;
    }
    const permission = await Notification.requestPermission();
    setNotifPermission(permission);
    if (permission === "granted") {
      setStatus("Уведомления устройства включены");
      new Notification("AidaMentor", { body: "Теперь я смогу прислать итоги дня на устройство." });
    } else {
      setError("Разрешение на уведомления не выдано");
    }
  };

  const sendDeviceDigest = async () => {
    await runAction(async () => {
      const digest = await api.getDigest();
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        new Notification("AidaMentor — итоги дня", { body: digest.body.slice(0, 240) });
      }
      return { ok: true, detail: "Итоги дня показаны на устройстве" };
    });
  };

  if (!settings) {
    return (
      <div className="section-view">
        <span className="section-icon">
          <Send size={28} />
        </span>
        <h2 className="section-heading">Интеграции</h2>
        <p className="section-text">{error ?? "Загрузка настроек…"}</p>
        {error && <div className="toast">{error}</div>}
      </div>
    );
  }

  return (
    <div className="integrations">
      <div className="integrations-head">
        <h2 className="section-heading">Интеграции</h2>
        <p className="section-text">
          Подключите Telegram для напоминаний, email-дайджест с итогами дня и уведомления устройства.
          Дайджест с итогами дня отправляется сервером автоматически в выбранное время.
        </p>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Send size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Telegram-напоминания</span>
            <StatusNote
              ok={settings.telegram_configured}
              onLabel="Бот на сервере настроен"
              offLabel="BOT__TOKEN не задан на сервере"
            />
          </div>
          <Switch
            on={settings.telegram_enabled}
            disabled={saving}
            onToggle={() => void patch({ telegram_enabled: !settings.telegram_enabled })}
          />
        </div>
        <label className="field">
          <span className="field-label">Чат или ID пользователя</span>
          <input
            className="field-input"
            value={fields.telegram_chat_id}
            placeholder="Например, @aida_chat"
            onChange={(e) => setFields((prev) => ({ ...prev, telegram_chat_id: e.target.value }))}
            onBlur={() => void patch({ telegram_chat_id: fields.telegram_chat_id || null })}
          />
        </label>
        <p className="settings-hint">
          Откройте бота в Telegram и отправьте <b>/start</b> — он ответит и запомнит ваш chat id
          автоматически.
        </p>
        <div className="settings-save">
          <button
            className="primary-btn sm"
            onClick={() => void runAction(api.testTelegram)}
            disabled={saving}
          >
            Отправить тест
          </button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Mail size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Email-дайджест</span>
            <StatusNote
              ok={settings.email_configured}
              onLabel="SMTP настроен"
              offLabel="SMTP не настроен (MAIL__HOST)"
            />
          </div>
          <Switch
            on={settings.email_digest_enabled}
            disabled={saving}
            onToggle={() => void patch({ email_digest_enabled: !settings.email_digest_enabled })}
          />
        </div>
        <div className="field-row">
          <label className="field">
            <span className="field-label">Адрес почты</span>
            <input
              className="field-input"
              type="email"
              value={fields.email_address}
              placeholder="you@example.com"
              onChange={(e) => setFields((prev) => ({ ...prev, email_address: e.target.value }))}
              onBlur={() => void patch({ email_address: fields.email_address || null })}
            />
          </label>
          <label className="field">
            <span className="field-label">Время отправки</span>
            <input
              className="field-input"
              type="time"
              value={fields.digest_time}
              onChange={(e) => setFields((prev) => ({ ...prev, digest_time: e.target.value }))}
              onBlur={() => void patch({ digest_time: fields.digest_time })}
            />
          </label>
        </div>
        <div className="settings-save">
          <button
            className="primary-btn sm"
            onClick={() => void runAction(api.testEmail)}
            disabled={saving}
          >
            Отправить тест
          </button>
          <button
            className="primary-btn sm"
            onClick={() =>
              void runAction(async () => {
                const digest = await api.runDigest();
                const failed = digest.channels.filter(([, state]) => state !== "sent");
                return {
                  ok: failed.length === 0,
                  detail:
                    digest.channels.length === 0
                      ? "Включите Telegram или email, чтобы отправить дайджест"
                      : `Отправлено: ${digest.channels.map(([channel]) => channel).join(", ")}`,
                };
              })
            }
            disabled={saving}
          >
            <Play size={14} /> Отправить дайджест сейчас
          </button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Bell size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Уведомления устройства</span>
            <StatusNote
              ok={notifPermission === "granted"}
              onLabel="Разрешение выдано"
              offLabel="Пока не разрешены"
            />
          </div>
        </div>
        <div className="settings-save">
          <button className="primary-btn sm" onClick={() => void enableDeviceNotifications()}>
            Разрешить уведомления
          </button>
          <button className="primary-btn sm" onClick={() => void sendDeviceDigest()}>
            Показать итоги дня
          </button>
        </div>
      </div>

      <div className="settings-card">
        <div className="settings-card-head">
          <span className="settings-card-icon">
            <Timer size={18} />
          </span>
          <div className="settings-card-titles">
            <span className="settings-card-title">Длина фокус-сессии</span>
            <span className="settings-card-sub">Длительность помодоро-интервала</span>
          </div>
        </div>
        <label className="field">
          <span className="field-label">Минуты</span>
          <input
            className="field-input"
            type="number"
            min={1}
            max={180}
            value={fields.pomodoro_minute}
            onChange={(e) =>
              setFields((prev) => ({ ...prev, pomodoro_minute: Number(e.target.value) }))
            }
            onBlur={() => {
              void patch({ pomodoro_minute: fields.pomodoro_minute });
              pomodoro.setFocusMinutes(fields.pomodoro_minute, true);
            }}
          />
        </label>
      </div>

      {status && <div className="toast toast-ok">{status}</div>}
      {error && <div className="toast">{error}</div>}
    </div>
  );
}
