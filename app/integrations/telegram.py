import httpx

TELEGRAM_API_BASE = "https://api.telegram.org"


class TelegramError(RuntimeError):
    """Raised when a Telegram Bot API call fails."""


class TelegramClient:
    """Thin async wrapper over the Telegram Bot API `sendMessage` method."""

    def __init__(self, token: str | None, *, timeout: float = 15.0) -> None:
        self._token = token or ""
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def ready(self) -> bool:
        return bool(self._token)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def send_message(self, chat_id: str, text: str) -> None:
        if not self.ready:
            raise TelegramError("Telegram bot token is not configured (BOT__TOKEN)")
        if not chat_id.strip():
            raise TelegramError(
                "Telegram chat id is not set — open «Интеграции» and save one"
            )

        url = f"{TELEGRAM_API_BASE}/bot{self._token}/sendMessage"
        try:
            response = await self._get_client().post(
                url,
                json={"chat_id": chat_id.strip(), "text": text},
            )
        except httpx.HTTPError as exc:
            raise TelegramError(f"Telegram request failed ({type(exc).__name__}): {exc}") from exc

        if response.status_code != 200:
            raise TelegramError(
                f"Telegram API returned {response.status_code}: {response.text[:300]}"
            )

    async def get_me(self) -> dict[str, object]:
        if not self.ready:
            raise TelegramError("Telegram bot token is not configured (BOT__TOKEN)")
        url = f"{TELEGRAM_API_BASE}/bot{self._token}/getMe"
        try:
            response = await self._get_client().get(url)
        except httpx.HTTPError as exc:
            raise TelegramError(f"Telegram request failed ({type(exc).__name__}): {exc}") from exc
        if response.status_code != 200:
            raise TelegramError(
                f"Telegram API returned {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
        return payload.get("result", {}) if isinstance(payload, dict) else {}

    async def get_updates(
        self,
        *,
        offset: int = 0,
        poll_timeout: int = 30,
    ) -> list[dict[str, object]]:
        """Long-poll Telegram for new updates."""
        if not self.ready:
            raise TelegramError("Telegram bot token is not configured (BOT__TOKEN)")
        url = f"{TELEGRAM_API_BASE}/bot{self._token}/getUpdates"
        try:
            response = await self._get_client().post(
                url,
                json={
                    "offset": offset,
                    "timeout": poll_timeout,
                    "allowed_updates": ["message", "edited_message"],
                },
                timeout=poll_timeout + 10,
            )
        except httpx.HTTPError as exc:
            raise TelegramError(f"Telegram request failed ({type(exc).__name__}): {exc}") from exc
        if response.status_code != 200:
            raise TelegramError(
                f"Telegram API returned {response.status_code}: {response.text[:300]}"
            )
        payload = response.json()
        result = payload.get("result", []) if isinstance(payload, dict) else []
        return [item for item in result if isinstance(item, dict)]

    async def delete_webhook(self) -> None:
        if not self.ready:
            return
        url = f"{TELEGRAM_API_BASE}/bot{self._token}/deleteWebhook"
        try:
            response = await self._get_client().post(url, json={"drop_pending_updates": False})
        except httpx.HTTPError as exc:
            raise TelegramError(f"Telegram request failed ({type(exc).__name__}): {exc}") from exc
        if response.status_code != 200:
            raise TelegramError(
                f"Telegram API returned {response.status_code}: {response.text[:300]}"
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
