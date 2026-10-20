from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.settings import AppSettingsModel


async def get_settings(session: AsyncSession) -> AppSettingsModel:
    stmt = select(AppSettingsModel).order_by(AppSettingsModel.id).limit(1)
    settings = await session.scalar(stmt)
    if settings is None:
        settings = AppSettingsModel()
        session.add(settings)
        await session.flush()
    return settings


async def change_settings(
    session: AsyncSession,
    *,
    changes: Mapping[str, object],
) -> AppSettingsModel:
    settings = await get_settings(session)
    for field, value in changes.items():
        setattr(settings, field, value)
    await session.flush()
    return settings
