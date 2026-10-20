import asyncio
import contextlib
import logging
from datetime import date, timedelta
from functools import lru_cache

from app.core.config import cfg
from app.database.crud import ai as ai_crud
from app.database.crud import context as context_crud
from app.database.crud import plan as plan_crud
from app.database.crud import schedule as schedule_crud
from app.database.crud import settings as settings_crud
from app.database.engine import Session
from app.database.models.chat import MessageRole
from app.database.models.plan import PlanTaskModel
from app.database.models.schedule import ScheduleEventModel
from app.domain.types.plan import PlanStage
from app.integrations.telegram import TelegramClient, TelegramError
from app.services.ai_config import (
    effective_max_tokens,
    effective_model,
    effective_provider,
    effective_system_prompt,
    effective_temperature,
)
from app.services.context import build_context_block
from app.services.digest import build_digest
from app.services.llm import DEFAULT_SYSTEM_PROMPT, ChatTurn, Persona, get_llm_service

logger = logging.getLogger(__name__)

POLL_TIMEOUT = 30
MAX_HISTORY = 12
MAX_MESSAGE_LEN = 3800

STAGE_LABELS: dict[str, str] = {
    PlanStage.IDEAS: "Идеи",
    PlanStage.PROGRESS: "В работе",
    PlanStage.REVIEW: "На проверке",
    PlanStage.DONE: "Готово",
}

GREETING = (
    "Привет! Я AidaMentor — ваш личный наставник.\n\n"
    "Напишите, чем помочь: разберём задачи, спланируем день, "
    "поставим цель и не потеряем фокус.\n\n"
    "Команды:\n"
    "/today — расписание на сегодня\n"
    "/tomorrow — план на завтра\n"
    "/tasks — задачи из раздела «Планы»\n"
    "/goal — текущая цель\n"
    "/digest — итоги дня и план на завтра\n"
    "/reset — очистить контекст диалога\n"
    "/id — узнать ваш chat id"
)


def _fmt_minute(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _event_line(event: ScheduleEventModel) -> str:
    start = _fmt_minute(event.start_minute)
    end = _fmt_minute(event.start_minute + event.duration_minute)
    detail = f" — {event.detail}" if event.detail else ""
    return f"• {start}–{end}  {event.title}{detail}"


def _extract_message(update: dict[str, object]) -> tuple[int, str] | None:
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    text = message.get("text")
    if not isinstance(chat_id, int) or not isinstance(text, str) or not text.strip():
        return None
    return chat_id, text.strip()


class TelegramBotRunner:
    """Long-polling Telegram bot that answers messages with the configured LLM."""

    def __init__(self) -> None:
        self._client = TelegramClient(cfg.bot.token.get_secret_value())
        self._history: dict[int, list[ChatTurn]] = {}
        self._offset = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return cfg.bot.type == "polling" and self._client.ready

    def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._client.close()

    async def _run(self) -> None:
        with contextlib.suppress(TelegramError):
            await self._client.delete_webhook()
        delay = 3.0
        while True:
            try:
                updates = await self._client.get_updates(
                    offset=self._offset, poll_timeout=POLL_TIMEOUT
                )
                delay = 3.0
            except TelegramError as exc:
                logger.warning("Telegram getUpdates failed: %s (retry in %.0fs)", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)
                continue
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    self._offset = max(self._offset, update_id + 1)
                extracted = _extract_message(update)
                if extracted is None:
                    continue
                chat_id, text = extracted
                try:
                    await self._handle(chat_id, text)
                except Exception:  # noqa: BLE001 - never let one update kill the loop
                    logger.exception("Failed to handle Telegram update")

    async def _handle(self, chat_id: int, text: str) -> None:
        await self._remember_chat(chat_id)
        command = text.split(maxsplit=1)[0].lower().split("@")[0]

        if command in ("/start", "/help"):
            await self._reply(chat_id, GREETING)
            return
        if command == "/id":
            await self._reply(chat_id, f"Ваш chat id: {chat_id}")
            return
        if command == "/today":
            await self._reply(chat_id, await self._day_summary(0))
            return
        if command == "/tomorrow":
            await self._reply(chat_id, await self._day_summary(1))
            return
        if command == "/tasks":
            await self._reply(chat_id, await self._tasks_summary())
            return
        if command == "/goal":
            await self._reply(chat_id, await self._goal_summary())
            return
        if command == "/digest":
            await self._reply(chat_id, await self._digest())
            return
        if command == "/reset":
            self._history.pop(chat_id, None)
            await self._reply(chat_id, "Контекст диалога очищен. Начнём заново.")
            return

        answer = await self._generate(chat_id, text)
        await self._reply(chat_id, answer)

    async def _day_summary(self, offset: int) -> str:
        target = date.today() + timedelta(days=offset)
        async with Session() as session:
            events = await schedule_crud.get_event_list(session, start=target, end=target)
        label = "Сегодня" if offset == 0 else "Завтра"
        header = f"{label} · {target.strftime('%d.%m.%Y')}"
        lines = [header]
        if not events:
            lines.append("")
            lines.append("Событий нет. Хорошее время, чтобы запланировать день.")
            return "\n".join(lines)
        lines.append("")
        for event in events:
            lines.append(_event_line(event))
        return "\n".join(lines)

    async def _tasks_summary(self) -> str:
        async with Session() as session:
            tasks = await plan_crud.get_task_list(session)
        if not tasks:
            return "Задач пока нет. Добавьте первую в разделе «Планы»."
        grouped: dict[str, list[PlanTaskModel]] = {}
        for task in tasks:
            grouped.setdefault(str(task.stage), []).append(task)
        lines = [f"Задачи ({len(tasks)})"]
        for stage, label in STAGE_LABELS.items():
            bucket = grouped.get(str(stage), [])
            if not bucket:
                continue
            lines.append("")
            lines.append(f"{label} — {len(bucket)}")
            for task in bucket[:8]:
                lines.append(f"  • {task.title}")
            extra = len(bucket) - 8
            if extra > 0:
                lines.append(f"  … и ещё {extra}")
        return "\n".join(lines)

    async def _goal_summary(self) -> str:
        async with Session() as session:
            goal = await plan_crud.get_goal(session)
        lines = [f"Цель: {goal.title}"]
        if goal.description.strip():
            lines.append(goal.description.strip())
        if goal.deadline is not None:
            lines.append(f"Дедлайн: {goal.deadline.strftime('%d.%m.%Y')}")
        return "\n".join(lines)

    async def _digest(self) -> str:
        async with Session() as session:
            body = await build_digest(session)
            await session.commit()
        return body

    async def _data_block(self) -> str:
        """Compact snapshot of today's schedule, tasks and goal for the LLM."""
        today = date.today()
        async with Session() as session:
            events = await schedule_crud.get_event_list(session, start=today, end=today)
            goal = await plan_crud.get_goal(session)
            tasks = await plan_crud.get_task_list(session)
        lines = ["Данные пользователя на сегодня:"]
        if events:
            lines.append("Расписание: " + "; ".join(_event_line(event).strip() for event in events))
        else:
            lines.append("Расписание: пусто")
        active = [task for task in tasks if task.stage is not PlanStage.DONE]
        lines.append(f"Задачи: в работе {len(active)}, всего {len(tasks)}")
        if goal.title:
            lines.append(f"Цель: {goal.title}")
        return "\n".join(lines)

    async def _remember_chat(self, chat_id: int) -> None:
        async with Session() as session:
            settings = await settings_crud.get_settings(session)
            if not settings.telegram_chat_id:
                settings.telegram_chat_id = str(chat_id)
                await session.commit()

    async def _generate(self, chat_id: int, text: str) -> str:
        history = self._history.setdefault(chat_id, [])
        history.append(ChatTurn(role=MessageRole.USER, content=text))
        persona = await self._persona()
        turns = history[-MAX_HISTORY:]
        try:
            answer = await get_llm_service().complete(persona, turns)
        except Exception as exc:  # noqa: BLE001 - report any provider failure to the user
            logger.warning("Telegram LLM reply failed: %s", exc)
            answer = "Сейчас не удалось получить ответ — модель недоступна. Попробуйте позже."
        if answer:
            history.append(ChatTurn(role=MessageRole.AI, content=answer))
        if len(history) > MAX_HISTORY:
            del history[:-MAX_HISTORY]
        return answer or "…"

    async def _persona(self) -> Persona:
        async with Session() as session:
            context = await context_crud.get_context(session)
            context_block = build_context_block(context)
            config = await ai_crud.get_config(session)
        provider = effective_provider(config)
        base = effective_system_prompt(config) or DEFAULT_SYSTEM_PROMPT
        blocks = [block for block in (base, context_block, await self._data_block()) if block]
        prompt = "\n\n".join(blocks)
        return Persona(
            system_prompt=prompt,
            provider=provider,
            model=effective_model(config, provider),
            temperature=effective_temperature(config),
            max_tokens=effective_max_tokens(config),
        )

    async def _reply(self, chat_id: int, text: str) -> None:
        try:
            await self._client.send_message(str(chat_id), text[:MAX_MESSAGE_LEN])
        except TelegramError as exc:
            logger.warning("Failed to send Telegram reply: %s", exc)


@lru_cache(maxsize=1)
def get_telegram_runner() -> TelegramBotRunner:
    return TelegramBotRunner()
