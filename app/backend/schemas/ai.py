from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types.ai import AiProvider


class AiCreate(BaseModel):
    provider: AiProvider
    model: str = Field(min_length=1, max_length=100)
    name: str = Field(default="AidaMentor", min_length=1, max_length=50)
    role: str = Field(default="You're Personality AI Assistant", min_length=1)
    character: str = Field(default="Tiny", min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class AiUpdate(BaseModel):
    provider: AiProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    role: str | None = Field(default=None, min_length=1)
    character: str | None = Field(default=None, min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)


class AiRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: AiProvider
    model: str
    name: str
    role: str
    character: str
    temperature: float


class AiConfigUpdate(BaseModel):
    provider: Literal["groq", "ollama"] | None = None
    model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=32768)
    system_prompt: str | None = Field(default=None, max_length=4000)


class AiConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str | None
    model: str | None
    temperature: float | None
    max_tokens: int | None
    system_prompt: str | None
    effective_provider: str
    effective_model: str | None
    effective_temperature: float
    effective_max_tokens: int


class AiModelInfo(BaseModel):
    provider: str
    model: str
    label: str


class AiModelsRead(BaseModel):
    provider: str
    models: list[AiModelInfo]
    error: str | None = None
