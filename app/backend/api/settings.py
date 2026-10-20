from fastapi import APIRouter

from app.backend.dependencies import SessionDep
from app.backend.schemas import (
    DigestRead,
    IntegrationTestRead,
    PomodoroComplete,
    SettingsRead,
    SettingsUpdate,
)
from app.core.config import cfg
from app.database.crud import settings as settings_crud
from app.integrations.mail import MailClient, MailError
from app.integrations.telegram import TelegramClient, TelegramError
from app.services.digest import build_digest, resolve_telegram_chat_id, send_digest

router = APIRouter(prefix="/settings", tags=["settings"])


def _read(settings: object) -> SettingsRead:
    data = SettingsRead.model_validate(settings)
    return data.model_copy(
        update={
            "telegram_configured": cfg.bot.token.get_secret_value() != "",
            "email_configured": cfg.mail.ready,
        }
    )


@router.get("", response_model=SettingsRead)
async def get_settings(session: SessionDep) -> SettingsRead:
    settings = await settings_crud.get_settings(session)
    await session.commit()
    return _read(settings)


@router.patch("", response_model=SettingsRead)
async def update_settings(payload: SettingsUpdate, session: SessionDep) -> SettingsRead:
    settings = await settings_crud.change_settings(
        session, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return _read(settings)


@router.post("/telegram/test", response_model=IntegrationTestRead)
async def test_telegram(session: SessionDep) -> IntegrationTestRead:
    settings = await settings_crud.get_settings(session)
    chat_id = resolve_telegram_chat_id(settings)
    if chat_id is None:
        return IntegrationTestRead(
            ok=False,
            detail=(
                "Chat id не задан. Откройте бота в Telegram и отправьте /start — "
                "он запомнит ваш chat id автоматически."
            ),
        )
    client = TelegramClient(cfg.bot.token.get_secret_value())
    try:
        await client.send_message(
            chat_id,
            "AidaMentor: тестовое уведомление. Канал Telegram работает.",
        )
    except TelegramError as exc:
        return IntegrationTestRead(ok=False, detail=str(exc))
    finally:
        await client.close()
    return IntegrationTestRead(ok=True, detail="Сообщение отправлено в Telegram")


@router.post("/email/test", response_model=IntegrationTestRead)
async def test_email(session: SessionDep) -> IntegrationTestRead:
    settings = await settings_crud.get_settings(session)
    mail = MailClient()
    try:
        await mail.send(
            to=settings.email_address or "",
            subject="AidaMentor — тестовое письмо",
            body="Это тестовое письмо.\n\nЕсли вы его читаете, email-дайджест настроен корректно.",
        )
    except MailError as exc:
        return IntegrationTestRead(ok=False, detail=str(exc))
    return IntegrationTestRead(ok=True, detail="Тестовое письмо отправлено")


@router.post("/pomodoro/complete", response_model=IntegrationTestRead)
async def pomodoro_complete(
    payload: PomodoroComplete, session: SessionDep
) -> IntegrationTestRead:
    settings = await settings_crud.get_settings(session)
    await session.commit()

    if not settings.telegram_enabled:
        return IntegrationTestRead(ok=False, detail="Telegram-напоминания выключены")

    chat_id = resolve_telegram_chat_id(settings)
    if chat_id is None:
        return IntegrationTestRead(
            ok=False,
            detail=(
                "Chat id не задан. Откройте бота в Telegram и отправьте /start — "
                "он запомнит ваш chat id автоматически."
            ),
        )

    finished = "Фокус-сессия завершена" if payload.phase == "focus" else "Перерыв завершён"
    hint = (
        "Пора сделать короткий перерыв."
        if payload.phase == "focus"
        else "Можно возвращаться к работе."
    )
    length = f" ({payload.minutes} мин)" if payload.minutes else ""
    client = TelegramClient(cfg.bot.token.get_secret_value())
    try:
        await client.send_message(chat_id, f"AidaMentor: {finished}{length}. {hint}")
    except TelegramError as exc:
        return IntegrationTestRead(ok=False, detail=str(exc))
    finally:
        await client.close()
    return IntegrationTestRead(ok=True, detail="Уведомление отправлено в Telegram")


@router.get("/digest", response_model=DigestRead)
async def preview_digest(session: SessionDep) -> DigestRead:
    body = await build_digest(session)
    await session.commit()
    return DigestRead(body=body, channels=[])


@router.post("/digest/run", response_model=DigestRead)
async def run_digest(session: SessionDep) -> DigestRead:
    result = await send_digest(session)
    await session.commit()
    return DigestRead(body=result.body, channels=result.channels)
