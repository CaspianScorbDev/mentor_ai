from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.database.models.chat import MessageRole


class SourceItem(BaseModel):
    title: str
    url: str
    snippet: str = ""


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    content: str
    thinking: str | None = None
    sources: list[SourceItem] | None = None
    created_at: datetime


class ChatCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, min_length=1)
    ai_id: int | None = None


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    ai_id: int | None
    created_at: datetime
    updated_at: datetime


class ChatDetail(ChatRead):
    messages: list[MessageRead]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    voice: bool = False
    deep_thinking: bool = False
    web_search: bool = False
    code_mode: bool = False
    files_mode: bool = False


class RegenerateRequest(BaseModel):
    """Flags only — regenerate reuses the existing last user message."""

    voice: bool = False
    deep_thinking: bool = False
    web_search: bool = False
    code_mode: bool = False
    files_mode: bool = False
