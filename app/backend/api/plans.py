from fastapi import APIRouter, status

from app.backend.dependencies import SessionDep
from app.backend.schemas import (
    GoalCreate,
    GoalRead,
    GoalUpdate,
    SubtaskCreate,
    SubtaskRead,
    SubtaskUpdate,
    TaskCreate,
    TaskRead,
    TaskUpdate,
)
from app.database.crud import plan as plan_crud

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/projects", response_model=list[GoalRead])
async def list_projects(session: SessionDep) -> list[GoalRead]:
    goals = await plan_crud.ensure_goal_list(session)
    await session.commit()
    return [GoalRead.model_validate(goal) for goal in goals]


@router.post("/projects", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
async def create_project(payload: GoalCreate, session: SessionDep) -> GoalRead:
    goal = await plan_crud.create_goal(
        session,
        title=payload.title,
        description=payload.description,
        deadline=payload.deadline,
    )
    await session.commit()
    return GoalRead.model_validate(goal)


@router.patch("/projects/{goal_id}", response_model=GoalRead)
async def update_project(
    goal_id: int, payload: GoalUpdate, session: SessionDep
) -> GoalRead:
    goal = await plan_crud.change_goal(
        session, changes=payload.model_dump(exclude_unset=True), goal_id=goal_id
    )
    await session.commit()
    return GoalRead.model_validate(goal)


@router.delete("/projects/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(goal_id: int, session: SessionDep) -> None:
    await plan_crud.delete_goal(session, goal_id)
    await session.commit()


@router.get("/goal", response_model=GoalRead)
async def get_goal(session: SessionDep) -> GoalRead:
    goal = await plan_crud.get_goal(session)
    await session.commit()
    return GoalRead.model_validate(goal)


@router.patch("/goal", response_model=GoalRead)
async def update_goal(payload: GoalUpdate, session: SessionDep) -> GoalRead:
    goal = await plan_crud.change_goal(
        session, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return GoalRead.model_validate(goal)


@router.get("/tasks", response_model=list[TaskRead])
async def list_tasks(
    session: SessionDep,
    limit: int = 500,
    offset: int = 0,
) -> list[TaskRead]:
    tasks = await plan_crud.get_task_list(session, limit=limit, offset=offset)
    return [TaskRead.model_validate(task) for task in tasks]


@router.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(payload: TaskCreate, session: SessionDep) -> TaskRead:
    task = await plan_crud.create_task(
        session,
        title=payload.title,
        stage=payload.stage,
        category=payload.category,
        goal_id=payload.goal_id,
        deadline=payload.deadline,
        assignee=payload.assignee,
    )
    await session.commit()
    await session.refresh(task, ["subtasks"])
    return TaskRead.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(task_id: int, session: SessionDep) -> TaskRead:
    task = await plan_crud.get_task(session, task_id)
    return TaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
async def update_task(task_id: int, payload: TaskUpdate, session: SessionDep) -> TaskRead:
    task = await plan_crud.change_task(
        session, task_id, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return TaskRead.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, session: SessionDep) -> None:
    await plan_crud.delete_task(session, task_id)
    await session.commit()


@router.post(
    "/tasks/{task_id}/subtasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_subtask(
    task_id: int, payload: SubtaskCreate, session: SessionDep
) -> TaskRead:
    await plan_crud.create_subtask(session, task_id=task_id, title=payload.title)
    task = await plan_crud.get_task(session, task_id)
    await session.commit()
    await session.refresh(task, ["subtasks"])
    return TaskRead.model_validate(task)


@router.patch("/subtasks/{subtask_id}", response_model=SubtaskRead)
async def update_subtask(
    subtask_id: int, payload: SubtaskUpdate, session: SessionDep
) -> SubtaskRead:
    subtask = await plan_crud.change_subtask(
        session, subtask_id, changes=payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return SubtaskRead.model_validate(subtask)


@router.delete("/subtasks/{subtask_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subtask(subtask_id: int, session: SessionDep) -> None:
    await plan_crud.delete_subtask(session, subtask_id)
    await session.commit()
