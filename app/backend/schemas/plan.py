from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.domain.types.category import Category
from app.domain.types.plan import PlanStage


class GoalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    deadline: date | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    deadline: date | None = None


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    deadline: date | None


class SubtaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class SubtaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    done: bool | None = None


class SubtaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    stage: PlanStage = PlanStage.IDEAS
    category: Category = Category.WORK
    goal_id: int | None = None
    deadline: str | None = Field(default=None, max_length=64)
    assignee: str | None = Field(default=None, max_length=64)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    stage: PlanStage | None = None
    category: Category | None = None
    goal_id: int | None = None
    deadline: str | None = Field(default=None, max_length=64)
    assignee: str | None = Field(default=None, max_length=64)


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    stage: PlanStage
    category: Category
    goal_id: int | None
    deadline: str | None
    assignee: str | None
    subtasks: list[SubtaskRead]
