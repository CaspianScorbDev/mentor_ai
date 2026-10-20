from datetime import datetime

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.database.crud import settings as settings_crud
from app.services import scheduler as scheduler_module
from app.services.digest import DigestResult


@pytest_asyncio.fixture
async def scheduler(
    db_engine: AsyncEngine, monkeypatch
) -> scheduler_module.DigestScheduler:
    maker = async_sessionmaker(db_engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(scheduler_module, "Session", maker)
    return scheduler_module.DigestScheduler()


async def test_scheduler_sends_once_per_day(
    session: AsyncSession, scheduler: scheduler_module.DigestScheduler, monkeypatch
) -> None:
    await settings_crud.change_settings(
        session,
        changes={
            "telegram_enabled": True,
            "email_digest_enabled": False,
            "digest_time": "08:30",
        },
    )
    await session.commit()

    calls: list[int] = []

    async def fake_send_digest(_session: AsyncSession) -> DigestResult:
        calls.append(1)
        return DigestResult(body="digest", channels=[("telegram", "sent")])

    monkeypatch.setattr(scheduler_module, "send_digest", fake_send_digest)

    moment = datetime(2030, 1, 1, 8, 30, tzinfo=scheduler.timezone)

    assert await scheduler.tick(now=moment) is True
    assert len(calls) == 1

    assert await scheduler.tick(now=moment) is False
    assert len(calls) == 1


async def test_scheduler_ignores_other_times(
    session: AsyncSession, scheduler: scheduler_module.DigestScheduler, monkeypatch
) -> None:
    await settings_crud.change_settings(
        session,
        changes={"telegram_enabled": True, "digest_time": "08:30"},
    )
    await session.commit()

    calls: list[int] = []

    async def fake_send_digest(_session: AsyncSession) -> DigestResult:
        calls.append(1)
        return DigestResult(body="digest", channels=[])

    monkeypatch.setattr(scheduler_module, "send_digest", fake_send_digest)

    other = datetime(2030, 1, 1, 9, 15, tzinfo=scheduler.timezone)

    assert await scheduler.tick(now=other) is False
    assert calls == []


async def test_scheduler_skips_when_disabled(
    session: AsyncSession, scheduler: scheduler_module.DigestScheduler, monkeypatch
) -> None:
    await settings_crud.change_settings(
        session,
        changes={
            "telegram_enabled": False,
            "email_digest_enabled": False,
            "digest_time": "08:30",
        },
    )
    await session.commit()

    async def fake_send_digest(_session: AsyncSession) -> DigestResult:
        raise AssertionError("send_digest must not run when integrations are disabled")

    monkeypatch.setattr(scheduler_module, "send_digest", fake_send_digest)

    moment = datetime(2030, 1, 1, 8, 30, tzinfo=scheduler.timezone)

    assert await scheduler.tick(now=moment) is False
