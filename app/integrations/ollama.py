import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.integrations.base import Message, OpenAICompatibleClient, StreamChunk

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:3b"


class OllamaClient(OpenAICompatibleClient):
    """Local Ollama chat API (OpenAI-compatible, with native `think` support)."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "ollama",
        timeout: float = 120.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=timeout,
            # qwen3* models reason before answering by default, adding seconds of
            # latency. Ollama's OpenAI-compat endpoint ignores `think`, but honours
            # `reasoning_effort: "none"`, which skips the reasoning pass entirely.
            extra_body={"reasoning_effort": "none"},
        )
        self._http: httpx.AsyncClient | None = None

    async def close(self) -> None:
        await super().close()
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    def _native_url(self) -> str:
        root = self.base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        return f"{root}/api/chat"

    def _http_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    async def _stream_native(
        self,
        messages: Sequence[Message],
        *,
        model: str | None,
        temperature: float,
        max_tokens: int,
        think: bool,
    ) -> AsyncIterator[StreamChunk]:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": list(messages),
            "stream": True,
            # Ollama's OpenAI-compatible endpoint ignores `think`, so the native
            # one is used for every stream. `think=False` guarantees no reasoning
            # pass (critical for voice) and `think=True` surfaces it as a channel.
            "think": think,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        async with self._http_client().stream(
            "POST", self._native_url(), json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if data.get("done"):
                    break
                message = data.get("message") or {}
                thinking = message.get("thinking")
                if thinking:
                    yield StreamChunk("thinking", thinking)
                content = message.get("content")
                if content:
                    yield StreamChunk("content", content)

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        think: bool = False,
    ) -> AsyncIterator[StreamChunk]:
        async for chunk in self._stream_native(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            think=think,
        ):
            yield chunk
