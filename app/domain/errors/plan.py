from app.domain.errors.domain import DomainError


class PlanGoalNotFoundError(DomainError):
    def __init__(self, goal_id: int | None = None) -> None:
        detail = f"Plan goal {goal_id} not found" if goal_id is not None else "Plan goal not found"
        super().__init__(detail)


class PlanTaskNotFoundError(DomainError):
    def __init__(self, task_id: int) -> None:
        super().__init__(f"Plan task {task_id} not found")


class PlanSubtaskNotFoundError(DomainError):
    def __init__(self, subtask_id: int) -> None:
        super().__init__(f"Plan subtask {subtask_id} not found")
