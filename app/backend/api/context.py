from fastapi import APIRouter

from app.backend.dependencies import SessionDep
from app.backend.schemas import ContextRead, ContextUpdate
from app.database.crud import context as context_crud
from app.database.models.context import UserContextModel
from app.services.context import is_configured

router = APIRouter(prefix="/context", tags=["context"])


def _read(model: UserContextModel) -> ContextRead:
    data = ContextRead.model_validate(model)
    return data.model_copy(update={"configured": is_configured(model)})


@router.get("", response_model=ContextRead)
async def get_context(session: SessionDep) -> ContextRead:
    context = await context_crud.get_context(session)
    await session.commit()
    return _read(context)


@router.patch("", response_model=ContextRead)
async def update_context(payload: ContextUpdate, session: SessionDep) -> ContextRead:
    context = await context_crud.change_context(
        session, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return _read(context)
