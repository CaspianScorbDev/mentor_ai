from sqlalchemy import BigInteger, CheckConstraint, Float, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.database.base import Base, TimestampMixin
from app.domain.types.ai import AiProvider


class AiSystemModel(Base):
    __tablename__ = "ai_system"
    __table_args__ = (
        CheckConstraint(
            "temperature >= 0.0 AND temperature <= 2.0",
            name="temperature_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[AiProvider] = mapped_column(
        SQLEnum(
            AiProvider,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
            length=32,
            name="ai_provider",
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(50), default="AidaMentor", nullable=False)
    role: Mapped[str] = mapped_column(
        Text, default="You're Personality AI Assistant", nullable=False
    )
    character: Mapped[str] = mapped_column(Text, default="Tiny", nullable=False)

    temperature: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)

    @validates("temperature")
    def validate_temperature(self, key, value):
        if not (0.0 <= value <= 2.0):
            raise ValueError(f"Parameter '{key}' must be between 0.0 and 2.0. Given: {value}")
        return value


class AiConfigModel(TimestampMixin, Base):
    """Singleton with the user-editable LLM preferences (all fields optional)."""

    __tablename__ = "ai_config"
    __table_args__ = (
        CheckConstraint(
            "temperature IS NULL OR (temperature >= 0.0 AND temperature <= 2.0)",
            name="ai_config_temperature_range",
        ),
        CheckConstraint(
            "max_tokens IS NULL OR (max_tokens >= 1 AND max_tokens <= 32768)",
            name="ai_config_max_tokens_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True, default=None)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

