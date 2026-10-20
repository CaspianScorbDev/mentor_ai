from fastapi import APIRouter
from sqlalchemy import text

from app.backend.dependencies import SessionDep
from app.backend.schemas import HealthRead
from app.core.config import cfg

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthRead)
async def health(session: SessionDep) -> HealthRead:
    await session.execute(text("SELECT 1"))
    return HealthRead(status="ok", version=cfg.application.version)
