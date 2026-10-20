import asyncio
import contextlib
import logging
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from app.core.config import cfg
from app.database.crud import settings as settings_crud
from app.database.engine import Session
from app.services.digest import send_digest

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 20.0


class DigestScheduler:
    """Sends the daily Telegram/email digest at the configured local time.

    Runs as a lightweight background task for the whole application lifetime.
    The last-sent day is tracked in memory, so a digest is delivered at most
    once per day per running process.
    """

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._last_sent: str | None = None
        self._tz = ZoneInfo(cfg.application.timezone)

    @property
    def timezone(self) -> ZoneInfo:
        return self._tz

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - scheduler must survive any failure
                logger.exception("Digest scheduler tick failed")
            await asyncio.sleep(CHECK_INTERVAL)

    async def tick(self, *, now: datetime | None = None) -> bool:
        """Send the digest if the local clock matches the configured time.

        Returns True when a digest was dispatched on this tick.
        """
        moment = now.astimezone(self._tz) if now is not None else datetime.now(self._tz)
        today = moment.date().isoformat()
        current = moment.strftime("%H:%M")
        if self._last_sent == today:
            return False

        async with Session() as session:
            settings = await settings_crud.get_settings(session)
            if not (settings.telegram_enabled or settings.email_digest_enabled):
                return False
            if settings.digest_time != current:
                return False
            result = await send_digest(session)
            await session.commit()

        self._last_sent = today
        logger.info("Daily digest dispatched via %s", result.channels or "no channels")
        return True


@lru_cache(maxsize=1)
def get_digest_scheduler() -> DigestScheduler:
    return DigestScheduler()
