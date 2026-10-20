from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.context import UserContextModel


async def get_context(session: AsyncSession) -> UserContextModel:
    stmt = select(UserContextModel).order_by(UserContextModel.id).limit(1)
    context = await session.scalar(stmt)
    if context is None:
        context = UserContextModel()
        session.add(context)
        await session.flush()
    return context


async def change_context(
    session: AsyncSession,
    *,
    changes: Mapping[str, object],
) -> UserContextModel:
    context = await get_context(session)
    for field, value in changes.items():
        setattr(context, field, value)
    await session.flush()
    return context
