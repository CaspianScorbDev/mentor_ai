from datetime import date as _Date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types.category import Category


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    date: _Date
    start: int = Field(ge=0, le=1439)
    duration: int = Field(gt=0, le=1440)
    category: Category = Category.WORK
    detail: str | None = None


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    date: _Date | None = None
    start: int | None = Field(default=None, ge=0, le=1439)
    duration: int | None = Field(default=None, gt=0, le=1440)
    category: Category | None = None
    detail: str | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    title: str
    date: _Date = Field(validation_alias="event_date")
    start: int = Field(validation_alias="start_minute")
    duration: int = Field(validation_alias="duration_minute")
    category: Category
    detail: str | None
