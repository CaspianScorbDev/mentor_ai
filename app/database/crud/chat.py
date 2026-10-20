from collections.abc import Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.chat import ChatModel, MessageModel, MessageRole
from app.domain.errors.chat import ChatModelNotFoundError, MessageNotFoundError


async def create_chat(
    session: AsyncSession,
    *,
    message: str | None = None,
    role: MessageRole = MessageRole.USER,
    title: str | None = None,
    ai_id: int | None = None,
) -> ChatModel:
    chat = ChatModel(title=title, ai_id=ai_id)
    if message is not None:
        chat.messages.append(MessageModel(role=role, content=message))
    session.add(chat)
    await session.flush()
    return chat


async def get_chat(session: AsyncSession, chat_id: int) -> ChatModel:
    chat = await session.get(ChatModel, chat_id)
    if chat is None:
        raise ChatModelNotFoundError(chat_id)
    return chat


async def get_chats(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[ChatModel]:
    stmt = (
        select(ChatModel)
        .order_by(ChatModel.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.scalars(stmt)
    return result.all()


async def add_message(
    session: AsyncSession,
    chat_id: int,
    *,
    role: MessageRole,
    content: str,
    thinking: str | None = None,
    sources: list[dict[str, str]] | None = None,
) -> MessageModel:
    message = MessageModel(
        chat_id=chat_id,
        role=role,
        content=content,
        thinking=thinking or None,
        sources=sources or None,
    )
    session.add(message)
    await session.flush()
    return message


async def get_recent_messages(
    session: AsyncSession,
    chat_id: int,
    *,
    limit: int,
) -> list[MessageModel]:
    stmt = (
        select(MessageModel)
        .where(MessageModel.chat_id == chat_id)
        .order_by(MessageModel.id.desc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return list(reversed(result.all()))


async def get_all_messages(session: AsyncSession, chat_id: int) -> list[MessageModel]:
    stmt = (
        select(MessageModel)
        .where(MessageModel.chat_id == chat_id)
        .order_by(MessageModel.id)
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def get_message(session: AsyncSession, message_id: int) -> MessageModel:
    message = await session.get(MessageModel, message_id)
    if message is None:
        raise MessageNotFoundError(message_id)
    return message


async def update_message_content(session: AsyncSession, message_id: int, *, content: str) -> None:
    stmt = update(MessageModel).where(MessageModel.id == message_id).values(content=content)
    await session.execute(stmt)


async def delete_messages_after(session: AsyncSession, chat_id: int, message_id: int) -> None:
    stmt = delete(MessageModel).where(
        MessageModel.chat_id == chat_id, MessageModel.id > message_id
    )
    await session.execute(stmt)


async def delete_last_ai_message(session: AsyncSession, chat_id: int) -> None:
    stmt = (
        select(MessageModel.id)
        .where(MessageModel.chat_id == chat_id, MessageModel.role == MessageRole.AI)
        .order_by(MessageModel.id.desc())
        .limit(1)
    )
    last_id = await session.scalar(stmt)
    if last_id is None:
        return
    await session.execute(delete(MessageModel).where(MessageModel.id == last_id))


async def delete_chat(session: AsyncSession, chat_id: int) -> None:
    chat = await get_chat(session, chat_id)
    await session.delete(chat)
    await session.flush()
