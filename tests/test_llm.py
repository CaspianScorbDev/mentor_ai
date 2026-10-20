from app.core.config import LlmSettings
from app.database.models.chat import MessageRole
from app.integrations import ollama as ollama_module
from app.integrations.ollama import OllamaClient
from app.services.llm import (
    DEFAULT_SYSTEM_PROMPT,
    ChatTurn,
    LLMService,
    build_system_prompt,
    to_openai_messages,
)


def test_build_system_prompt_with_character() -> None:
    prompt = build_system_prompt("You are a mentor", "warm and patient")
    assert "You are a mentor" in prompt
    assert "warm and patient" in prompt


def test_build_system_prompt_empty_falls_back() -> None:
    assert build_system_prompt("", None) == DEFAULT_SYSTEM_PROMPT


def test_build_system_prompt_does_not_duplicate_character() -> None:
    prompt = build_system_prompt("You are a warm mentor", "warm")
    assert prompt == "You are a warm mentor"


def test_to_openai_messages_maps_roles() -> None:
    turns = [
        ChatTurn(role=MessageRole.USER, content="hi"),
        ChatTurn(role=MessageRole.AI, content="hello"),
        ChatTurn(role=MessageRole.SYSTEM, content="note"),
    ]
    messages = to_openai_messages("sys", turns, window=10)
    assert messages[0] == {"role": "system", "content": "sys"}
    assert [m["role"] for m in messages[1:]] == ["user", "assistant", "system"]


def test_to_openai_messages_respects_window() -> None:
    turns = [ChatTurn(role=MessageRole.USER, content=str(i)) for i in range(10)]
    messages = to_openai_messages("sys", turns, window=3)
    assert len(messages) == 4
    assert [m["content"] for m in messages[1:]] == ["7", "8", "9"]


def test_provider_order_prefers_persona_then_default() -> None:
    service = LLMService(LlmSettings(provider="ollama"))
    order = service._provider_order("groq")
    assert order[0] == "groq"
    assert order[1] == "ollama"
    assert len(order) == len(set(order))


def test_provider_order_deduplicates() -> None:
    service = LLMService(LlmSettings(provider="groq"))
    assert service._provider_order("groq") == ["groq", "ollama"]


def test_ollama_native_url_strips_v1() -> None:
    client = OllamaClient(base_url="http://localhost:11434/v1")
    assert client._native_url() == "http://localhost:11434/api/chat"


class _FakeResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response

    async def __aenter__(self) -> _FakeResponse:
        return self._response

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeHttpxClient:
    captured: dict[str, object] = {}

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeHttpxClient":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def stream(self, method: str, url: str, json: dict | None = None) -> _FakeStreamCtx:
        _FakeHttpxClient.captured = {"method": method, "url": url, "json": json}
        return _FakeStreamCtx(
            _FakeResponse(
                [
                    '{"message":{"thinking":"hmm"},"done":false}',
                    '{"message":{"content":"Hel"},"done":false}',
                    '{"message":{"content":"lo"},"done":false}',
                    '{"done":true}',
                ]
            )
        )


async def test_ollama_think_uses_native_api(monkeypatch) -> None:
    monkeypatch.setattr(ollama_module.httpx, "AsyncClient", _FakeHttpxClient)
    client = OllamaClient(base_url="http://localhost:11434/v1")

    chunks = [
        chunk async for chunk in client.stream([{"role": "user", "content": "hi"}], think=True)
    ]

    assert [(c.kind, c.text) for c in chunks] == [
        ("thinking", "hmm"),
        ("content", "Hel"),
        ("content", "lo"),
    ]
    assert str(_FakeHttpxClient.captured["url"]).endswith("/api/chat")
    assert _FakeHttpxClient.captured["json"]["think"] is True  # type: ignore[index]

