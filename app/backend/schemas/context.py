from pydantic import BaseModel, ConfigDict, Field


class ContextUpdate(BaseModel):
    user_name: str | None = Field(default=None, max_length=120)
    current_goal: str | None = Field(default=None, max_length=4000)
    specialization: str | None = Field(default=None, max_length=120)
    communication_style: str | None = Field(default=None, max_length=120)
    mentor_tone: str | None = Field(default=None, max_length=120)
    interests: str | None = Field(default=None, max_length=4000)
    language: str | None = Field(default=None, max_length=32)
    mentor_mode: bool | None = None
    use_schedule: bool | None = None
    use_plans: bool | None = None


class ContextRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_name: str
    current_goal: str
    specialization: str
    communication_style: str
    mentor_tone: str
    interests: str
    language: str
    mentor_mode: bool
    use_schedule: bool
    use_plans: bool
    configured: bool = False
