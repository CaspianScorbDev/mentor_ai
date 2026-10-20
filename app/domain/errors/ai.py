from app.domain.errors.domain import DomainError


class AiModelNotFoundError(DomainError):
    def __init__(self, ai_id: int) -> None:
        super().__init__(f"Ai {ai_id} not found")


class LlmUnavailableError(DomainError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"LLM provider unavailable: {detail}")
