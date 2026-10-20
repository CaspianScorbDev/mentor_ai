from app.domain.errors.domain import DomainError


class ChatModelNotFoundError(DomainError):
    def __init__(self, chat_id: int) -> None:
        super().__init__(f"Chat {chat_id} not found")


class MessageNotFoundError(DomainError):
    def __init__(self, message_id: int) -> None:
        super().__init__(f"Message {message_id} not found")