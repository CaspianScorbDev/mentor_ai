import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import cfg
from app.database.crud import ai as ai_crud
from app.database.crud import chat as chat_crud
from app.database.crud import context as context_crud
from app.database.models.ai import AiSystemModel
from app.database.models.chat import ChatModel, MessageModel, MessageRole
from app.services.ai_config import (
    effective_max_tokens,
    effective_model,
    effective_provider,
    effective_system_prompt,
    effective_temperature,
)
from app.services.context import build_context_block
from app.services.llm import (
    DEFAULT_SYSTEM_PROMPT,
    PROVIDER_BY_AI,
    ChatTurn,
    LLMService,
    Persona,
    build_system_prompt,
)

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Ты суммируешь историю диалога между пользователем и AI-наставником. "
    "Сохрани ключевые факты, решения, договорённости, названия и даты. "
    "Пиши по-русски, одним плотным абзацем, без воды. "
    "Максимум 250 слов. Не добавляй вступлений и заголовков."
)

SUMMARY_TAIL = 4
SUMMARY_THRESHOLD = 4


def turns_from_messages(
    messages: Sequence[MessageModel],
    *,
    summary: str | None = None,
) -> list[ChatTurn]:
    turns: list[ChatTurn] = []
    if summary:
        turns.append(
            ChatTurn(role=MessageRole.SYSTEM, content=f"Итог предыдущего диалога: {summary}")
        )
    turns.extend(
        ChatTurn(role=message.role, content=message.content) for message in messages
    )
    return turns


def _with_context(system_prompt: str, context_block: str) -> str:
    if not context_block:
        return system_prompt
    return f"{system_prompt}\n\n{context_block}"


async def load_persona(session: AsyncSession, chat: ChatModel) -> Persona:
    context = await context_crud.get_context(session)
    context_block = build_context_block(context)

    if chat.ai_id is not None:
        ai = await session.get(AiSystemModel, chat.ai_id)
        if ai is not None:
            provider = PROVIDER_BY_AI.get(ai.provider)
            return Persona(
                system_prompt=_with_context(
                    build_system_prompt(ai.role, ai.character), context_block
                ),
                provider=provider,
                model=ai.model if provider is not None else None,
                temperature=ai.temperature,
            )

    config = await ai_crud.get_config(session)
    provider = effective_provider(config)
    extra_prompt = effective_system_prompt(config)
    return Persona(
        system_prompt=_with_context(extra_prompt or DEFAULT_SYSTEM_PROMPT, context_block),
        provider=provider,
        model=effective_model(config, provider),
        temperature=effective_temperature(config),
        max_tokens=effective_max_tokens(config),
    )


async def _summarize_turns(
    llm: LLMService,
    base: Persona,
    turns: Sequence[ChatTurn],
) -> str:
    persona = Persona(
        system_prompt=SUMMARY_PROMPT,
        provider=base.provider,
        model=base.model,
        temperature=0.2,
        max_tokens=512,
    )
    dialogue = "\n".join(f"{turn.role.value}: {turn.content}" for turn in turns)
    return await llm.complete(
        persona,
        [
            ChatTurn(
                role=MessageRole.USER,
                content=f"Сводка диалога:\n{dialogue}",
            )
        ],
    )


async def ensure_summary(
    session: AsyncSession,
    chat: ChatModel,
    llm: LLMService,
) -> None:
    """Fold older messages into a running summary so long chats stay coherent.

    The most recent `context_messages` turns are always kept verbatim; anything
    older is compressed into `chat.summary` and reused on the next request.
    """
    window = cfg.llm.context_messages
    messages = await chat_crud.get_all_messages(session, chat.id)
    if len(messages) <= window + SUMMARY_THRESHOLD:
        return

    upto = chat.summary_upto or 0
    fresh = [message for message in messages if message.id > upto]
    if len(fresh) <= window:
        return

    pending = fresh[: len(fresh) - window]
    if not pending:
        return

    try:
        base = await load_persona(session, chat)
        produced = await _summarize_turns(llm, base, turns_from_messages(pending))
    except Exception:  # noqa: BLE001 - summarization must never break the chat
        logger.warning("history summarization failed for chat %s", chat.id, exc_info=True)
        return

    produced = produced.strip()
    if not produced:
        return

    previous = (chat.summary or "").strip()
    chat.summary = f"{previous}\n\n{produced}".strip() if previous else produced
    chat.summary_upto = pending[-1].id
    await session.flush()
