from httpx import AsyncClient

from app.backend.api import settings as settings_api

API = "/api/v1"


class _FakeTelegram:
    def __init__(self, *args: object, **kwargs: object) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))

    async def close(self) -> None:
        return None


async def test_settings_defaults(client: AsyncClient) -> None:
    response = await client.get(f"{API}/settings")
    assert response.status_code == 200
    body = response.json()
    assert "telegram_enabled" in body
    assert "digest_time" in body


async def test_settings_update(client: AsyncClient) -> None:
    updated = await client.patch(
        f"{API}/settings",
        json={
            "telegram_enabled": True,
            "telegram_chat_id": "123456",
            "digest_time": "08:30",
            "pomodoro_minute": 30,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["telegram_enabled"] is True
    assert body["telegram_chat_id"] == "123456"
    assert body["digest_time"] == "08:30"
    assert body["pomodoro_minute"] == 30

    toggled = await client.patch(
        f"{API}/settings", json={"telegram_enabled": False, "telegram_chat_id": None}
    )
    assert toggled.status_code == 200
    assert toggled.json()["telegram_enabled"] is False
    assert toggled.json()["telegram_chat_id"] is None


async def test_settings_validation(client: AsyncClient) -> None:
    response = await client.patch(f"{API}/settings", json={"digest_time": "oops"})
    assert response.status_code == 422


async def test_settings_reports_configured_flags(client: AsyncClient) -> None:
    response = await client.get(f"{API}/settings")
    assert response.status_code == 200
    body = response.json()
    assert "telegram_configured" in body
    assert "email_configured" in body


async def test_telegram_test_without_chat_id_reports_error(
    client: AsyncClient, monkeypatch
) -> None:
    await client.patch(
        f"{API}/settings",
        json={"telegram_enabled": False, "telegram_chat_id": None},
    )
    monkeypatch.setattr(settings_api, "resolve_telegram_chat_id", lambda _settings: None)
    response = await client.post(f"{API}/settings/telegram/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["detail"]


async def test_telegram_test_uses_fallback_chat_id(
    client: AsyncClient, monkeypatch
) -> None:
    fake = _FakeTelegram()
    monkeypatch.setattr(settings_api, "resolve_telegram_chat_id", lambda _settings: "42")
    monkeypatch.setattr(settings_api, "TelegramClient", lambda *_args, **_kwargs: fake)
    response = await client.post(f"{API}/settings/telegram/test")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake.sent and fake.sent[0][0] == "42"


async def test_email_test_without_address_reports_error(client: AsyncClient) -> None:
    await client.patch(f"{API}/settings", json={"email_address": None})
    response = await client.post(f"{API}/settings/email/test")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False


async def test_pomodoro_complete_disabled_reports_off(client: AsyncClient) -> None:
    await client.patch(f"{API}/settings", json={"telegram_enabled": False})
    response = await client.post(
        f"{API}/settings/pomodoro/complete", json={"phase": "focus", "minutes": 25}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "выключ" in body["detail"].lower()


async def test_pomodoro_complete_sends_via_telegram(client: AsyncClient, monkeypatch) -> None:
    fake = _FakeTelegram()
    monkeypatch.setattr(settings_api, "resolve_telegram_chat_id", lambda _settings: "42")
    monkeypatch.setattr(settings_api, "TelegramClient", lambda *_args, **_kwargs: fake)
    await client.patch(f"{API}/settings", json={"telegram_enabled": True})

    response = await client.post(
        f"{API}/settings/pomodoro/complete", json={"phase": "focus", "minutes": 25}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fake.sent and fake.sent[0][0] == "42"
    assert "Фокус-сессия" in fake.sent[0][1]


async def test_digest_run_builds_body(client: AsyncClient) -> None:
    await client.patch(
        f"{API}/settings",
        json={"telegram_enabled": False, "email_digest_enabled": False},
    )
    response = await client.post(f"{API}/settings/digest/run")
    assert response.status_code == 200
    body = response.json()
    assert "AidaMentor" in body["body"]
    assert body["channels"] == []

