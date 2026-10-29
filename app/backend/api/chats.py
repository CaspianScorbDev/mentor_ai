import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.backend.dependencies import LLMServiceDep, SessionDep
from app.backend.schemas import (
    ChatCreate,
    ChatDetail,
    ChatRead,
    MessageCreate,
    MessageRead,
    RegenerateRequest,
)
from app.core.config import cfg
from app.core.logging import current_request_id
from app.database.crud import chat as chat_crud
from app.database.models.chat import MessageRole
from app.domain.errors.domain import DomainError
from app.integrations.search import SearchResult, search_web
from app.services import chat as chat_service
from app.services.llm import (
    CODE_MODE_PROMPT,
    FILES_MODE_PROMPT,
    VOICE_STYLE_PROMPT,
    WEB_SEARCH_PROMPT,
    ChatTurn,
    LLMService,
    Persona,
    strip_voice_tags,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])

SEARCH_UNAVAILABLE = "[Веб-поиск сейчас недоступен. Скажи об этом явно и ответь по своим знаниям.]"
SEARCH_EMPTY = "[Поиск не дал результатов. Ответь по своим знаниям.]"
VOICE_MAX_TOKENS = 400


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _search_prompt_block(results: list[SearchResult]) -> str:
    parts = [WEB_SEARCH_PROMPT, "Результаты поиска (актуальные, прочитаны со страниц):"]
    for index, result in enumerate(results, start=1):
        lines = [f"[{index}] {result.title}", f"URL: {result.url}"]
        if result.content:
            lines.append(f"Содержимое страницы: {result.content}")
        elif result.snippet:
            lines.append(f"Фрагмент: {result.snippet}")
        parts.append("\n".join(lines))
    parts.append(
        "Отвечай, опираясь на эти источники, и ссылайся на них номерами в квадратных "
        "скобках, например [1]. Не выдумывай факты, которых нет в источниках."
    )
    return "\n\n".join(parts)


def _sources_payload(results: list[SearchResult]) -> list[dict[str, str]]:
    return [
        {"title": r.title, "url": r.url, "snippet": (r.snippet or r.content)[:220]}
        for r in results
    ]


def _apply_flags(payload: MessageCreate | RegenerateRequest, persona: Persona) -> None:
    if payload.deep_thinking:
        persona.think = True
    if payload.code_mode:
        persona.system_prompt = f"{CODE_MODE_PROMPT}\n\n{persona.system_prompt}"
        persona.temperature = min(persona.temperature, 0.25)
    if payload.files_mode:
        persona.system_prompt = f"{persona.system_prompt}\n\n{FILES_MODE_PROMPT}"
    if payload.voice:
        # Spoken replies must start immediately: any reasoning pass is dead air
        # the user hears as silence, so voice always wins over deep thinking.
        persona.think = False
        persona.max_tokens = min(persona.max_tokens or cfg.llm.max_tokens, VOICE_MAX_TOKENS)
        persona.system_prompt = f"{persona.system_prompt}\n\n{VOICE_STYLE_PROMPT}"


async def _prepare(
    session: AsyncSession,
    chat_id: int,
    payload: MessageCreate | RegenerateRequest,
    llm: LLMService,
) -> tuple[Persona, list[ChatTurn]]:
    chat = await chat_crud.get_chat(session, chat_id)
    persona = await chat_service.load_persona(session, chat)
    _apply_flags(payload, persona)
    await chat_service.ensure_summary(session, chat, llm)
    history = await chat_crud.get_recent_messages(
        session, chat_id, limit=cfg.llm.context_messages
    )
    turns = chat_service.turns_from_messages(history, summary=chat.summary)
    # Everything above is plain data. Commit now so the pooled connection goes
    # back to the pool instead of being held for the whole SSE stream (which can
    # run 40s+ and starves the pool under concurrent load).
    await session.commit()
    return persona, turns


async def _save_partial(
    chat_id: int,
    *,
    content: str,
    thinking: str,
    sources: list[dict[str, str]] | None,
) -> None:
    """Persist a stopped answer so the transcript survives a disconnect."""
    from app.database.engine import Session

    async with Session() as session:
        await chat_crud.add_message(
            session,
            chat_id,
            role=MessageRole.AI,
            content=content,
            thinking=thinking or None,
            sources=sources,
        )
        await session.commit()


# Strong references keep fire-and-forget saves alive until they finish;
# an unreferenced task can be garbage-collected mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


def _persist_partial_in_background(
    chat_id: int,
    *,
    content: str,
    thinking: str,
    sources: list[dict[str, str]] | None,
) -> None:
    """Schedule the partial save without awaiting inside a cancelled task."""
    task = asyncio.get_running_loop().create_task(
        _save_partial(chat_id, content=content, thinking=thinking, sources=sources)
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def _reply_stream(
    *,
    llm: LLMService,
    session: AsyncSession,
    chat_id: int,
    payload: MessageCreate | RegenerateRequest,
    query: str,
    persona: Persona,
    turns: list[ChatTurn],
) -> AsyncIterator[str]:
    collected: list[str] = []
    collected_thinking: list[str] = []
    sources: list[dict[str, str]] | None = None

    if payload.web_search:
        yield _sse({"type": "status", "detail": "Ищу в интернете…"})
        try:
            results = await search_web(query)
        except Exception:  # noqa: BLE001 - search is best-effort
            results = None
        if results:
            sources = _sources_payload(results)
            yield _sse({"type": "sources", "items": sources})
            persona.system_prompt = (
                f"{persona.system_prompt}\n\n{_search_prompt_block(results)}"
            )
        else:
            notice = SEARCH_EMPTY if results == [] else SEARCH_UNAVAILABLE
            persona.system_prompt = (
                f"{persona.system_prompt}\n\n{WEB_SEARCH_PROMPT}\n\n{notice}"
            )

    try:
        async for chunk in llm.stream(persona, turns):
            if chunk.kind == "thinking":
                collected_thinking.append(chunk.text)
                yield _sse({"type": "thinking", "content": chunk.text})
            else:
                collected.append(chunk.text)
                yield _sse({"type": "delta", "content": chunk.text})
    except (asyncio.CancelledError, GeneratorExit):
        # The client asked us to stop (or went away); keep what was produced.
        answer = "".join(collected)
        if answer.strip():
            _persist_partial_in_background(
                chat_id,
                content=answer,
                thinking="".join(collected_thinking),
                sources=sources,
            )
        raise
    except DomainError as exc:
        logger.warning("domain error while streaming chat %s: %s", chat_id, exc)
        yield _sse({"type": "error", "detail": str(exc), "request_id": current_request_id()})
        return
    except Exception:  # noqa: BLE001 - never leak internals to the client
        logger.exception("stream failed for chat %s", chat_id)
        yield _sse(
            {
                "type": "error",
                "detail": f"Внутренняя ошибка при генерации ответа ({current_request_id()})",
                "request_id": current_request_id(),
            }
        )
        return

    answer = "".join(collected)
    if payload.voice:
        answer = strip_voice_tags(answer)
    thinking = "".join(collected_thinking)

    message = await chat_crud.add_message(
        session,
        chat_id,
        role=MessageRole.AI,
        content=answer,
        thinking=thinking or None,
        sources=sources,
    )
    await session.commit()
    yield _sse(
        {
            "type": "done",
            "message": MessageRead.model_validate(message).model_dump(mode="json"),
        }
    )


@router.get("", response_model=list[ChatRead])
async def list_chats(
    session: SessionDep,
    limit: int = 100,
    offset: int = 0,
) -> list[ChatRead]:
    chats = await chat_crud.get_chats(session, limit=limit, offset=offset)
    return [ChatRead.model_validate(chat) for chat in chats]


@router.post("", response_model=ChatDetail, status_code=status.HTTP_201_CREATED)
async def create_chat(payload: ChatCreate, session: SessionDep) -> ChatDetail:
    title = payload.title
    if title is None and payload.message is not None:
        title = payload.message[:60]

    chat = await chat_crud.create_chat(
        session,
        message=payload.message,
        title=title,
        ai_id=payload.ai_id,
    )
    await session.commit()
    await session.refresh(chat, attribute_names=["messages"])
    return ChatDetail.model_validate(chat)


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(chat_id: int, session: SessionDep) -> ChatDetail:
    chat = await chat_crud.get_chat(session, chat_id)
    return ChatDetail.model_validate(chat)


@router.get("/{chat_id}/messages", response_model=list[MessageRead])
async def list_messages(chat_id: int, session: SessionDep) -> list[MessageRead]:
    await chat_crud.get_chat(session, chat_id)
    messages = await chat_crud.get_recent_messages(
        session, chat_id, limit=cfg.llm.context_messages
    )
    return [MessageRead.model_validate(message) for message in messages]


@router.post("/{chat_id}/messages")
async def create_message(
    chat_id: int,
    payload: MessageCreate,
    session: SessionDep,
    llm: LLMServiceDep,
) -> StreamingResponse:
    logger.info("chat %s message (request %s)", chat_id, current_request_id())
    await chat_crud.get_chat(session, chat_id)
    await chat_crud.add_message(
        session, chat_id, role=MessageRole.USER, content=payload.content
    )
    await session.commit()

    persona, turns = await _prepare(session, chat_id, payload, llm)
    logger.debug("chat %s generated %s turns", chat_id, len(turns))
    return StreamingResponse(
        _reply_stream(
            llm=llm,
            session=session,
            chat_id=chat_id,
            payload=payload,
            query=payload.content,
            persona=persona,
            turns=turns,
        ),
        media_type="text/event-stream",
    )


@router.post("/{chat_id}/messages/regenerate")
async def regenerate_message(
    chat_id: int,
    payload: RegenerateRequest,
    session: SessionDep,
    llm: LLMServiceDep,
) -> StreamingResponse:
    """Drop the last AI answer and generate a fresh one from the same history."""
    logger.info("chat %s regenerate (request %s)", chat_id, current_request_id())
    await chat_crud.delete_last_ai_message(session, chat_id)
    await session.commit()

    history = await chat_crud.get_recent_messages(
        session, chat_id, limit=cfg.llm.context_messages
    )
    if not history or history[-1].role != MessageRole.USER:
        return StreamingResponse(
            iter([_sse({"type": "error", "detail": "Нечего перегенерировать."})]),
            media_type="text/event-stream",
        )

    persona, turns = await _prepare(session, chat_id, payload, llm)
    return StreamingResponse(
        _reply_stream(
            llm=llm,
            session=session,
            chat_id=chat_id,
            payload=payload,
            query=history[-1].content,
            persona=persona,
            turns=turns,
        ),
        media_type="text/event-stream",
    )


@router.put("/{chat_id}/messages/{message_id}")
async def edit_message(
    chat_id: int,
    message_id: int,
    payload: MessageCreate,
    session: SessionDep,
    llm: LLMServiceDep,
) -> StreamingResponse:
    """Rewrite a user message, drop everything after it and answer again."""
    logger.info("chat %s edit %s (request %s)", chat_id, message_id, current_request_id())
    message = await chat_crud.get_message(session, message_id)
    if message.chat_id != chat_id or message.role != MessageRole.USER:
        return StreamingResponse(
            iter(
                [
                    _sse(
                        {
                            "type": "error",
                            "detail": "Редактировать можно только свои сообщения.",
                        }
                    )
                ]
            ),
            media_type="text/event-stream",
        )

    await chat_crud.update_message_content(session, message_id, content=payload.content)
    await chat_crud.delete_messages_after(session, chat_id, message_id)
    await session.commit()

    persona, turns = await _prepare(session, chat_id, payload, llm)
    return StreamingResponse(
        _reply_stream(
            llm=llm,
            session=session,
            chat_id=chat_id,
            payload=payload,
            query=payload.content,
            persona=persona,
            turns=turns,
        ),
        media_type="text/event-stream",
    )


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(chat_id: int, session: SessionDep) -> None:
    await chat_crud.delete_chat(session, chat_id)
    await session.commit()
