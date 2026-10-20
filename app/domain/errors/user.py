from app.domain.errors.domain import DomainError


class UserModelNotFoundError(DomainError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"user {user_id} not found")