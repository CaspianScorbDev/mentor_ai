from fastapi import APIRouter

from app.backend.api import ai, chats, context, health, plans, schedule, settings, voice

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(chats.router)
api_router.include_router(ai.router)
api_router.include_router(context.router)
api_router.include_router(schedule.router)
api_router.include_router(plans.router)
api_router.include_router(settings.router)
api_router.include_router(voice.router)

__all__ = ["api_router"]
