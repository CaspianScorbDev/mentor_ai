from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, Date, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin
from app.domain.types.category import Category


class ScheduleEventModel(TimestampMixin, Base):
    __tablename__ = "schedule_events"
    __table_args__ = (
        CheckConstraint(
            "start_minute >= 0 AND start_minute < 1440",
            name="start_minute_range",
        ),
        CheckConstraint(
            "duration_minute > 0 AND duration_minute <= 1440",
            name="duration_minute_range",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    category: Mapped[Category] = mapped_column(
        SQLEnum(
            Category,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
            length=16,
            name="event_category",
        ),
        nullable=False,
        default=Category.WORK,
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
