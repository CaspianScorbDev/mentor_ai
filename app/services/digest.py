from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import cfg
from app.database.crud import plan as plan_crud
from app.database.crud import schedule as schedule_crud
from app.database.crud import settings as settings_crud
from app.database.models.plan import PlanGoalModel, PlanTaskModel
from app.database.models.schedule import ScheduleEventModel
from app.database.models.settings import AppSettingsModel
from app.domain.types.plan import PlanStage
from app.integrations.mail import MailClient, MailError
from app.integrations.telegram import TelegramClient, TelegramError

WEEKDAYS_RU = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)
MONTHS_RU = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

MAX_LISTED_EVENTS = 8
MAX_LISTED_TASKS = 6


def resolve_telegram_chat_id(settings: AppSettingsModel) -> str | None:
    """Pick a Telegram chat id: saved one, then configured notification/admin id."""
    saved = (settings.telegram_chat_id or "").strip()
    if saved:
        return saved
    if cfg.bot.notifications_chat_id is not None:
        return str(cfg.bot.notifications_chat_id)
    if cfg.bot.admin_ids:
        return str(cfg.bot.admin_ids[0])
    return None


def _fmt_time(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _date_label(day: date, today: date) -> str:
    if day == today:
        prefix = "Сегодня"
    elif day == today + timedelta(days=1):
        prefix = "Завтра"
    else:
        prefix = day.strftime("%d.%m")
    return f"{prefix} · {day.day} {MONTHS_RU[day.month - 1]}, {WEEKDAYS_RU[day.weekday()]}"


def _event_line(event: ScheduleEventModel) -> str:
    start = _fmt_time(event.start_minute)
    end = _fmt_time(event.start_minute + event.duration_minute)
    detail = f" — {event.detail}" if event.detail else ""
    return f"  {start}–{end}  {event.title}{detail}"


def _event_section(events: Sequence[ScheduleEventModel], today: date, day: date) -> list[str]:
    day_events = [event for event in events if event.event_date == day]
    lines = [_date_label(day, today), "  (пусто — запланируйте что-нибудь)"]
    if day_events:
        lines = [_date_label(day, today)]
        for event in day_events[:MAX_LISTED_EVENTS]:
            lines.append(_event_line(event))
        extra = len(day_events) - MAX_LISTED_EVENTS
        if extra > 0:
            lines.append(f"  … и ещё {extra}")
    return lines


def _task_line(task: PlanTaskModel) -> str:
    subtasks = list(task.subtasks)
    if subtasks:
        done = sum(1 for subtask in subtasks if subtask.done)
        return f"  • {task.title} ({done}/{len(subtasks)} подзадач)"
    return f"  • {task.title}"


def build_digest_body(
    *,
    events: list[ScheduleEventModel],
    goal: PlanGoalModel,
    tasks: list[PlanTaskModel],
) -> str:
    today = date.today()
    lines = ["AidaMentor — итоги дня и план на завтра", ""]

    lines.extend(_event_section(events, today, today))
    lines.append("")
    lines.extend(_event_section(events, today, today + timedelta(days=1)))
    lines.append("")

    lines.append(f"Цель: {goal.title}")
    if goal.description.strip():
        lines.append(f"  {goal.description.strip()}")
    if goal.deadline is not None:
        lines.append(f"  Дедлайн: {goal.deadline.strftime('%d.%m.%Y')}")
    lines.append("")

    active = [task for task in tasks if task.stage is not PlanStage.DONE]
    done = [task for task in tasks if task.stage is PlanStage.DONE]
    lines.append(f"Задачи: в работе {len(active)}, готово {len(done)}")
    for task in active[:MAX_LISTED_TASKS]:
        lines.append(_task_line(task))
    extra = len(active) - MAX_LISTED_TASKS
    if extra > 0:
        lines.append(f"  … и ещё {extra}")
    if not active:
        lines.append("  (нет активных задач — добавьте следующий шаг)")

    lines.append("")
    lines.append("— AidaMentor")
    return "\n".join(lines)


@dataclass(slots=True)
class DigestResult:
    body: str
    channels: list[tuple[str, str]] = field(default_factory=list)


async def build_digest(session: AsyncSession) -> str:
    today = date.today()
    events = await schedule_crud.get_event_list(
        session, start=today, end=today + timedelta(days=1)
    )
    goal = await plan_crud.get_goal(session)
    tasks = await plan_crud.get_task_list(session)
    return build_digest_body(events=list(events), goal=goal, tasks=list(tasks))


async def send_digest(session: AsyncSession) -> DigestResult:
    settings = await settings_crud.get_settings(session)
    today = date.today()
    body = await build_digest(session)
    result = DigestResult(body=body)

    if settings.telegram_enabled:
        client = TelegramClient(cfg.bot.token.get_secret_value())
        chat_id = resolve_telegram_chat_id(settings)
        try:
            if chat_id is None:
                raise TelegramError(
                    "Telegram chat id is not set — напишите боту в Telegram, чтобы он его запомнил"
                )
            await client.send_message(chat_id, body)
            result.channels.append(("telegram", "sent"))
        except TelegramError as exc:
            result.channels.append(("telegram", str(exc)))
        finally:
            await client.close()

    if settings.email_digest_enabled:
        mail = MailClient()
        try:
            await mail.send(
                to=settings.email_address or "",
                subject=f"AidaMentor — дайджест {today.strftime('%d.%m.%Y')}",
                body=body,
            )
            result.channels.append(("email", "sent"))
        except MailError as exc:
            result.channels.append(("email", str(exc)))

    return result
