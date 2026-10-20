from fastapi import APIRouter, Query, status

from app.backend.dependencies import SessionDep
from app.backend.schemas import (
    AiConfigRead,
    AiConfigUpdate,
    AiCreate,
    AiModelInfo,
    AiModelsRead,
    AiRead,
    AiUpdate,
)
from app.database.crud import ai as ai_crud
from app.database.models.ai import AiConfigModel
from app.services.ai_config import (
    SUPPORTED_PROVIDERS,
    effective_max_tokens,
    effective_model,
    effective_provider,
    effective_temperature,
    list_models,
)

router = APIRouter(prefix="/ai", tags=["ai"])


def _read_config(config: AiConfigModel) -> AiConfigRead:
    provider = effective_provider(config)
    return AiConfigRead(
        provider=config.provider,
        model=config.model,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        system_prompt=config.system_prompt,
        effective_provider=provider,
        effective_model=effective_model(config, provider),
        effective_temperature=effective_temperature(config),
        effective_max_tokens=effective_max_tokens(config),
    )


@router.get("", response_model=list[AiRead])
async def list_ai(session: SessionDep, limit: int = 100, offset: int = 0) -> list[AiRead]:
    models = await ai_crud.get_ai_list(session, limit=limit, offset=offset)
    return [AiRead.model_validate(model) for model in models]


@router.get("/config", response_model=AiConfigRead)
async def get_ai_config(session: SessionDep) -> AiConfigRead:
    config = await ai_crud.get_config(session)
    await session.commit()
    return _read_config(config)


@router.patch("/config", response_model=AiConfigRead)
async def update_ai_config(payload: AiConfigUpdate, session: SessionDep) -> AiConfigRead:
    config = await ai_crud.change_config(
        session, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return _read_config(config)


@router.get("/models", response_model=AiModelsRead)
async def available_models(
    provider: str = Query(default="ollama"),
) -> AiModelsRead:
    if provider not in SUPPORTED_PROVIDERS:
        provider = "ollama"
    names, error = await list_models(provider)
    return AiModelsRead(
        provider=provider,
        models=[AiModelInfo(provider=provider, model=name, label=name) for name in names],
        error=error,
    )


@router.post("", response_model=AiRead, status_code=status.HTTP_201_CREATED)
async def create_ai(payload: AiCreate, session: SessionDep) -> AiRead:
    model = await ai_crud.create_ai_model(
        session,
        provider=payload.provider,
        model=payload.model,
        name=payload.name,
        role=payload.role,
        character=payload.character,
        temperature=payload.temperature,
    )
    await session.commit()
    return AiRead.model_validate(model)


@router.get("/{ai_id}", response_model=AiRead)
async def get_ai(ai_id: int, session: SessionDep) -> AiRead:
    model = await ai_crud.get_ai(session, ai_id)
    return AiRead.model_validate(model)


@router.patch("/{ai_id}", response_model=AiRead)
async def update_ai(ai_id: int, payload: AiUpdate, session: SessionDep) -> AiRead:
    model = await ai_crud.change_ai_model(
        session,
        ai_id,
        provider=payload.provider,
        model=payload.model,
        name=payload.name,
        role=payload.role,
        character=payload.character,
        temperature=payload.temperature,
    )
    await session.commit()
    return AiRead.model_validate(model)
