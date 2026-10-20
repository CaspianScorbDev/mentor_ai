from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast

from openai import AsyncOpenAI

Message = dict[str, str]
StreamKind = Literal["content", "thinking"]


@dataclass(slots=True)
class StreamChunk:
    """One streamed piece of a completion, tagged with its channel."""

    kind: StreamKind
    text: str


class OpenAICompatibleClient:
    """Shared async wrapper around any OpenAI-compatible chat API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        timeout: float = 60.0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._extra_body = extra_body or {}
        self._client: AsyncOpenAI | None = None

    @property
    def ready(self) -> bool:
        return bool(self.api_key)

    def _get_client(self) -> AsyncOpenAI:
        if not self.ready:
            raise RuntimeError(f"{type(self).__name__} is not configured (missing api key)")
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        think: bool = False,
    ) -> AsyncIterator[StreamChunk]:
        del think  # only Ollama's native path consumes this flag
        client = self._get_client()
        stream = await client.chat.completions.create(
            model=model or self.model,
            messages=cast(Any, list(messages)),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            extra_body=self._extra_body,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = getattr(delta, "reasoning_content", None) or getattr(
                delta, "reasoning", None
            )
            if reasoning:
                yield StreamChunk("thinking", str(reasoning))
            if delta.content:
                yield StreamChunk("content", delta.content)

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        client = self._get_client()
        completion = await client.chat.completions.create(
            model=model or self.model,
            messages=cast(Any, list(messages)),
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=self._extra_body,
        )
        return completion.choices[0].message.content or ""

    async def is_available(self) -> bool:
        if not self.ready:
            return False
        try:
            await self._get_client().models.list()
            return True
        except Exception:
            return False

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> "OpenAICompatibleClient":
        self._get_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()
