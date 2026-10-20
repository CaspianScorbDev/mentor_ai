from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class UserContextModel(TimestampMixin, Base):
    __tablename__ = "user_context"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    current_goal: Mapped[str] = mapped_column(Text, nullable=False, default="")
    specialization: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    communication_style: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    mentor_tone: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    interests: Mapped[str] = mapped_column(Text, nullable=False, default="")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="Русский")
    mentor_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_schedule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    use_plans: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
