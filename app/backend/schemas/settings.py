from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PomodoroComplete(BaseModel):
    phase: Literal["focus", "break"] = "focus"
    minutes: int = Field(default=0, ge=0, le=600)


class SettingsUpdate(BaseModel):
    telegram_enabled: bool | None = None
    telegram_chat_id: str | None = Field(default=None, max_length=64)
    email_digest_enabled: bool | None = None
    email_address: str | None = Field(default=None, max_length=255)
    digest_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    pomodoro_minute: int | None = Field(default=None, ge=1, le=180)


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_enabled: bool
    telegram_chat_id: str | None
    email_digest_enabled: bool
    email_address: str | None
    digest_time: str
    pomodoro_minute: int
    telegram_configured: bool = False
    email_configured: bool = False


class IntegrationTestRead(BaseModel):
    ok: bool
    detail: str


class DigestRead(BaseModel):
    body: str
    channels: list[tuple[str, str]]
