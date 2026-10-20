from enum import StrEnum

from sqlalchemy import JSON, BigInteger, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class MessageRole(StrEnum):
    AI = "ai"
    USER = "user"
    SYSTEM = "system"


class ChatModel(TimestampMixin, Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    ai_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("ai_system.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    summary_upto: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, default=None
    )

    messages: Mapped[list["MessageModel"]] = relationship(
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="MessageModel.id",
    )
    

class MessageModel(TimestampMixin, Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(
            MessageRole,
            native_enum=False,
            values_callable=lambda e: [m.value for m in e],
            length=16,
            name="message_role",
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    sources: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    chat: Mapped["ChatModel"] = relationship(back_populates="messages")