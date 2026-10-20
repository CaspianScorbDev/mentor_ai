from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.ai import AiConfigModel, AiSystemModel
from app.domain.errors.ai import AiModelNotFoundError
from app.domain.types.ai import AiProvider


async def create_ai_model(
    session: AsyncSession,
    *,
    provider: AiProvider,
    model: str,
    name: str,
    role: str,
    character: str,
    temperature: float,
) -> AiSystemModel:
    ai_system = AiSystemModel(
        provider=provider,
        model=model,
        name=name,
        role=role,
        character=character,
        temperature=temperature,
    )
    session.add(ai_system)
    await session.flush()
    return ai_system


async def change_ai_model(
    session: AsyncSession,
    ai_id: int,
    *,
    provider: AiProvider | None = None,
    model: str | None = None,
    name: str | None = None,
    role: str | None = None,
    character: str | None = None,
    temperature: float | None = None,
) -> AiSystemModel:
    ai_system = await get_ai(session, ai_id)

    if provider is not None:
        ai_system.provider = provider
    if model is not None:
        ai_system.model = model
    if name is not None:
        ai_system.name = name
    if role is not None:
        ai_system.role = role
    if character is not None:
        ai_system.character = character
    if temperature is not None:
        ai_system.temperature = temperature

    await session.flush()
    return ai_system


async def get_ai(session: AsyncSession, ai_id: int) -> AiSystemModel:
    ai_system = await session.get(AiSystemModel, ai_id)
    if ai_system is None:
        raise AiModelNotFoundError(ai_id)
    return ai_system


async def get_ai_list(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[AiSystemModel]:
    stmt = (
        select(AiSystemModel)
        .order_by(AiSystemModel.id)
        .limit(limit)
        .offset(offset)
    )
    result = await session.scalars(stmt)
    return result.all()


async def get_config(session: AsyncSession) -> AiConfigModel:
    stmt = select(AiConfigModel).order_by(AiConfigModel.id).limit(1)
    config = await session.scalar(stmt)
    if config is None:
        config = AiConfigModel()
        session.add(config)
        await session.flush()
    return config


async def change_config(
    session: AsyncSession,
    *,
    changes: Mapping[str, object],
) -> AiConfigModel:
    config = await get_config(session)
    for field, value in changes.items():
        setattr(config, field, value)
    await session.flush()
    return config
