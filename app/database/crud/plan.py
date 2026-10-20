from collections.abc import Mapping, Sequence
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.plan import PlanGoalModel, PlanSubtaskModel, PlanTaskModel
from app.domain.errors.plan import (
    PlanGoalNotFoundError,
    PlanSubtaskNotFoundError,
    PlanTaskNotFoundError,
)
from app.domain.types.category import Category
from app.domain.types.plan import PlanStage

DEFAULT_GOAL_TITLE = "Цель на месяц"
DEFAULT_GOAL_DAYS = 30
STARTER_PROJECTS: tuple[tuple[str, str], ...] = (
    ("Личный рост", "Мини-проект для развития навыков и привычек."),
    ("Рабочий проект", "Мини-проект по основной работе или учёбе."),
)


async def get_goal(session: AsyncSession) -> PlanGoalModel:
    """Return the primary (first) project, creating a starter set if none exist."""
    stmt = select(PlanGoalModel).order_by(PlanGoalModel.id).limit(1)
    goal = await session.scalar(stmt)
    if goal is None:
        goal = PlanGoalModel(
            title=DEFAULT_GOAL_TITLE,
            description="Крупная цель, к которой ведут задачи.",
            deadline=date.today() + timedelta(days=DEFAULT_GOAL_DAYS),
        )
        session.add(goal)
        await session.flush()
    return goal


async def get_goal_list(session: AsyncSession) -> Sequence[PlanGoalModel]:
    stmt = select(PlanGoalModel).order_by(PlanGoalModel.id)
    result = await session.scalars(stmt)
    return result.all()


async def ensure_goal_list(session: AsyncSession) -> Sequence[PlanGoalModel]:
    """Seed a couple of mini-projects the first time the workspace is opened."""
    goals = await get_goal_list(session)
    if goals:
        return goals
    for title, description in STARTER_PROJECTS:
        session.add(
            PlanGoalModel(
                title=title,
                description=description,
                deadline=date.today() + timedelta(days=DEFAULT_GOAL_DAYS),
            )
        )
    await session.flush()
    return await get_goal_list(session)


async def get_goal_by_id(session: AsyncSession, goal_id: int) -> PlanGoalModel:
    goal = await session.get(PlanGoalModel, goal_id)
    if goal is None:
        raise PlanGoalNotFoundError(goal_id)
    return goal


async def create_goal(
    session: AsyncSession,
    *,
    title: str,
    description: str = "",
    deadline: date | None = None,
) -> PlanGoalModel:
    goal = PlanGoalModel(
        title=title,
        description=description,
        deadline=deadline
        if deadline is not None
        else date.today() + timedelta(days=DEFAULT_GOAL_DAYS),
    )
    session.add(goal)
    await session.flush()
    return goal


async def change_goal(
    session: AsyncSession,
    *,
    changes: Mapping[str, object],
    goal_id: int | None = None,
) -> PlanGoalModel:
    if goal_id is not None:
        goal = await get_goal_by_id(session, goal_id)
    else:
        goal = await get_goal(session)
    for field, value in changes.items():
        setattr(goal, field, value)
    await session.flush()
    return goal


async def delete_goal(session: AsyncSession, goal_id: int) -> None:
    goal = await get_goal_by_id(session, goal_id)
    await session.delete(goal)
    await session.flush()


async def create_task(
    session: AsyncSession,
    *,
    title: str,
    stage: PlanStage,
    category: Category,
    goal_id: int | None = None,
    deadline: str | None = None,
    assignee: str | None = None,
) -> PlanTaskModel:
    task = PlanTaskModel(
        title=title,
        stage=stage,
        category=category,
        goal_id=goal_id,
        deadline=deadline,
        assignee=assignee,
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(session: AsyncSession, task_id: int) -> PlanTaskModel:
    task = await session.get(PlanTaskModel, task_id)
    if task is None:
        raise PlanTaskNotFoundError(task_id)
    return task


async def get_task_list(
    session: AsyncSession,
    *,
    limit: int = 500,
    offset: int = 0,
) -> Sequence[PlanTaskModel]:
    stmt = select(PlanTaskModel).order_by(PlanTaskModel.id).limit(limit).offset(offset)
    result = await session.scalars(stmt)
    return result.all()


async def change_task(
    session: AsyncSession,
    task_id: int,
    *,
    changes: Mapping[str, object],
) -> PlanTaskModel:
    task = await get_task(session, task_id)
    for field, value in changes.items():
        setattr(task, field, value)
    await session.flush()
    return task


async def delete_task(session: AsyncSession, task_id: int) -> None:
    task = await get_task(session, task_id)
    await session.delete(task)
    await session.flush()


async def create_subtask(
    session: AsyncSession,
    *,
    task_id: int,
    title: str,
) -> PlanSubtaskModel:
    task = await get_task(session, task_id)
    subtask = PlanSubtaskModel(task_id=task.id, title=title)
    session.add(subtask)
    await session.flush()
    return subtask


async def get_subtask(session: AsyncSession, subtask_id: int) -> PlanSubtaskModel:
    subtask = await session.get(PlanSubtaskModel, subtask_id)
    if subtask is None:
        raise PlanSubtaskNotFoundError(subtask_id)
    return subtask


async def change_subtask(
    session: AsyncSession,
    subtask_id: int,
    *,
    changes: Mapping[str, object],
) -> PlanSubtaskModel:
    subtask = await get_subtask(session, subtask_id)
    for field, value in changes.items():
        setattr(subtask, field, value)
    await session.flush()
    return subtask


async def delete_subtask(session: AsyncSession, subtask_id: int) -> None:
    subtask = await get_subtask(session, subtask_id)
    await session.delete(subtask)
    await session.flush()
