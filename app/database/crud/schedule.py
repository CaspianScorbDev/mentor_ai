from collections.abc import Mapping, Sequence
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.schedule import ScheduleEventModel
from app.domain.errors.schedule import ScheduleEventNotFoundError
from app.domain.types.category import Category


async def create_event(
    session: AsyncSession,
    *,
    title: str,
    event_date: date,
    start_minute: int,
    duration_minute: int,
    category: Category,
    detail: str | None = None,
) -> ScheduleEventModel:
    event = ScheduleEventModel(
        title=title,
        event_date=event_date,
        start_minute=start_minute,
        duration_minute=duration_minute,
        category=category,
        detail=detail,
    )
    session.add(event)
    await session.flush()
    return event


async def get_event(session: AsyncSession, event_id: int) -> ScheduleEventModel:
    event = await session.get(ScheduleEventModel, event_id)
    if event is None:
        raise ScheduleEventNotFoundError(event_id)
    return event


async def get_event_list(
    session: AsyncSession,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 500,
    offset: int = 0,
) -> Sequence[ScheduleEventModel]:
    stmt = select(ScheduleEventModel)
    if start is not None:
        stmt = stmt.where(ScheduleEventModel.event_date >= start)
    if end is not None:
        stmt = stmt.where(ScheduleEventModel.event_date <= end)
    stmt = (
        stmt.order_by(ScheduleEventModel.event_date, ScheduleEventModel.start_minute)
        .limit(limit)
        .offset(offset)
    )
    result = await session.scalars(stmt)
    return result.all()


async def change_event(
    session: AsyncSession,
    event_id: int,
    *,
    changes: Mapping[str, object],
) -> ScheduleEventModel:
    event = await get_event(session, event_id)
    for field, value in changes.items():
        setattr(event, field, value)
    await session.flush()
    return event


async def delete_event(session: AsyncSession, event_id: int) -> None:
    event = await get_event(session, event_id)
    await session.delete(event)
    await session.flush()
