from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.domain.types.category import Category
from app.domain.types.plan import PlanStage



class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PlanGoalModel(TimestampMixin, Base):
    __tablename__ = "plan_goals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)

    tasks: Mapped[list["PlanTaskModel"]] = relationship(
        back_populates="goal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="PlanTaskModel.id",
    )


class PlanTaskModel(TimestampMixin, Base):
    __tablename__ = "plan_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    goal_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("plan_goals.id", ondelete="CASCADE"),
        nullable=True,
        default=None,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[PlanStage] = mapped_column(
        SQLEnum(
            PlanStage,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
            length=16,
            name="plan_stage",
        ),
        nullable=False,
        default=PlanStage.IDEAS,
    )
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
    deadline: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)
    assignee: Mapped[str | None] = mapped_column(String(64), nullable=True, default=None)

    goal: Mapped["PlanGoalModel | None"] = relationship(back_populates="tasks")
    subtasks: Mapped[list["PlanSubtaskModel"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="PlanSubtaskModel.id",
    )


class PlanSubtaskModel(TimestampMixin, Base):
    __tablename__ = "plan_subtasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("plan_tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    task: Mapped["PlanTaskModel"] = relationship(back_populates="subtasks")
