from typing import Literal

from pydantic import BaseModel, Field


class VoiceInfoRead(BaseModel):
    name: str
    title: str
    kind: Literal["builtin", "cloned"] = "builtin"
    language: str | None = None


class VoiceStatusRead(BaseModel):
    backend: str
    ready: bool
    model: str
    sample_rate: int
    default_voice: str | None = None
    detail: str | None = None
    voices: list[VoiceInfoRead] = Field(default_factory=list)


class VoiceSpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=40000)
    voice: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=1000)


class VoiceTranscriptRead(BaseModel):
    text: str
    language: str | None = None


__all__ = [
    "VoiceInfoRead",
    "VoiceSpeakRequest",
    "VoiceStatusRead",
    "VoiceTranscriptRead",
]
