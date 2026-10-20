from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient

import main
from app.backend.api import chats as chats_api
from app.integrations.base import StreamChunk
from app.integrations.search import SearchResult
from app.services.llm import ChatTurn, Persona, get_llm_service

API = "/api/v1"


class _ThinkingLLM:
    async def stream(
        self, persona: Persona, turns: list[ChatTurn]
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk("thinking", "let me reason ")
        yield StreamChunk("content", "the answer")

    async def close(self) -> None:
        return None


def _results() -> list[SearchResult]:
    return [
        SearchResult(
            title="FastAPI",
            url="https://fastapi.tiangolo.com",
            snippet="Docs snippet",
            content="FastAPI is a modern web framework.",
        ),
        SearchResult(title="Other", url="https://example.com", snippet="Snippet"),
    ]


def test_search_prompt_block_includes_sources_and_content() -> None:
    block = chats_api._search_prompt_block(_results())
    assert "FastAPI" in block
    assert "https://fastapi.tiangolo.com" in block
    assert "FastAPI is a modern web framework." in block
    assert "[1]" in block


def test_sources_payload_shape() -> None:
    payload = chats_api._sources_payload(_results())
    assert payload[0]["title"] == "FastAPI"
    assert payload[0]["url"] == "https://fastapi.tiangolo.com"
    assert payload[0]["snippet"]


async def test_message_with_tools_streams(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_search(query: str, *, limit: int = 5) -> list[SearchResult]:
        return _results()

    monkeypatch.setattr(chats_api, "search_web", fake_search)

    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Tools"})
    chat_id = created.json()["id"]

    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={
            "content": "latest news",
            "deep_thinking": False,
            "web_search": True,
            "code_mode": True,
            "files_mode": True,
        },
    )
    assert streamed.status_code == 200
    assert '"type": "status"' in streamed.text
    assert '"type": "sources"' in streamed.text
    assert '"type": "done"' in streamed.text


async def test_message_without_search_has_no_sources(client: AsyncClient) -> None:
    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Plain"})
    chat_id = created.json()["id"]

    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages", json={"content": "hello"}
    )
    assert streamed.status_code == 200
    assert '"type": "sources"' not in streamed.text


async def test_search_degrades_when_unavailable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(query: str, *, limit: int = 5) -> list[SearchResult]:
        raise RuntimeError("offline")

    monkeypatch.setattr(chats_api, "search_web", boom)

    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Offline"})
    chat_id = created.json()["id"]

    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"content": "news", "web_search": True},
    )
    assert streamed.status_code == 200
    assert '"type": "done"' in streamed.text
    assert '"type": "sources"' not in streamed.text


async def test_sources_persisted_on_message(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_search(query: str, *, limit: int = 5) -> list[SearchResult]:
        return _results()

    monkeypatch.setattr(chats_api, "search_web", fake_search)

    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Persist"})
    chat_id = created.json()["id"]
    await client.post(
        f"{API}/chats/{chat_id}/messages", json={"content": "news", "web_search": True}
    )

    detail = await client.get(f"{API}/chats/{chat_id}")
    ai_messages = [m for m in detail.json()["messages"] if m["role"] == "ai"]
    assert ai_messages
    sources = ai_messages[-1]["sources"]
    assert sources
    assert sources[0]["url"] == "https://fastapi.tiangolo.com"


async def test_thinking_persisted_on_message(client: AsyncClient) -> None:
    main.app.dependency_overrides[get_llm_service] = lambda: _ThinkingLLM()

    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Think"})
    chat_id = created.json()["id"]
    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages",
        json={"content": "why", "deep_thinking": True},
    )
    assert '"type": "thinking"' in streamed.text

    detail = await client.get(f"{API}/chats/{chat_id}")
    ai_messages = [m for m in detail.json()["messages"] if m["role"] == "ai"]
    assert ai_messages[-1]["thinking"] == "let me reason "
    assert ai_messages[-1]["content"] == "the answer"


async def test_regenerate_replaces_last_answer(client: AsyncClient) -> None:
    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Re"})
    chat_id = created.json()["id"]
    await client.post(f"{API}/chats/{chat_id}/messages", json={"content": "hello"})
    before = await client.get(f"{API}/chats/{chat_id}")
    assert len(before.json()["messages"]) == 3

    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages/regenerate", json={}
    )
    assert streamed.status_code == 200
    assert '"type": "done"' in streamed.text

    after = await client.get(f"{API}/chats/{chat_id}")
    messages = after.json()["messages"]
    assert len(messages) == 3
    assert messages[-2]["content"] == "hello"
    assert messages[-1]["content"] == "Hello!"


async def test_regenerate_without_user_message_fails_cleanly(client: AsyncClient) -> None:
    created = await client.post(f"{API}/chats", json={"title": "Empty"})
    chat_id = created.json()["id"]
    streamed = await client.post(f"{API}/chats/{chat_id}/messages/regenerate", json={})
    assert streamed.status_code == 200
    assert '"type": "error"' in streamed.text


async def test_edit_message_drops_trailing_messages(client: AsyncClient) -> None:
    created = await client.post(f"{API}/chats", json={"message": "hi", "title": "Edit"})
    chat_id = created.json()["id"]
    await client.post(f"{API}/chats/{chat_id}/messages", json={"content": "first"})
    await client.post(f"{API}/chats/{chat_id}/messages", json={"content": "second"})

    detail = await client.get(f"{API}/chats/{chat_id}")
    first_user = next(m for m in detail.json()["messages"] if m["content"] == "first")

    streamed = await client.put(
        f"{API}/chats/{chat_id}/messages/{first_user['id']}",
        json={"content": "reworded"},
    )
    assert streamed.status_code == 200
    assert '"type": "done"' in streamed.text

    after = await client.get(f"{API}/chats/{chat_id}")
    contents = [m["content"] for m in after.json()["messages"]]
    assert contents == ["hi", "reworded", "Hello!"]
