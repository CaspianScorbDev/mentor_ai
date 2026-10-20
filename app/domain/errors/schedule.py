from app.domain.errors.domain import DomainError


class ScheduleEventNotFoundError(DomainError):
    def __init__(self, event_id: int) -> None:
        super().__init__(f"Schedule event {event_id} not found")
