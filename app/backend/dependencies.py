from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.engine import get_session
from app.integrations.kitten import VoiceBackend, get_voice_backend
from app.services.llm import LLMService, get_llm_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
VoiceBackendDep = Annotated[VoiceBackend, Depends(get_voice_backend)]
