import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import LlmSettings, cfg
from app.database.models.chat import MessageRole
from app.domain.errors.ai import LlmUnavailableError
from app.domain.types.ai import AiProvider
from app.integrations.base import Message, OpenAICompatibleClient, StreamChunk
from app.integrations.groq import GroqClient
from app.integrations.ollama import OllamaClient

DEFAULT_SYSTEM_PROMPT = "You are AidaMentor, a friendly and supportive AI mentor."

VOICE_STYLE_PROMPT = (
    "Голосовой режим: отвечай кратко, живо и разговорно. Озвучка понимает "
    "интонационные теги — ставь их в начале фразы: [angry], [contemplative], "
    "[excited], [joyful], [mundane], [nervous], [sad], [stern], [surprised], "
    "[tender]. Для звуков вставляй тег в нужном месте: <gasp>, <giggle>, "
    "<growl>, <gulp>, <laugh>, <scoff>, <sigh>, <sob>. Подбирай теги под смысл "
    "фразы, не ставь их в каждой фразе. Не произноси теги словами и не "
    "объясняй их."
)

CODE_MODE_PROMPT = (
    "РЕЖИМ КОДА. Ты — senior software engineer с 15+ годами опыта. Правила:\n"
    "- Не говори что ты какой-то опытный senior software engineer с 15+ "
    "годами опыта. Если спросят какое у тебя расширение, говори: "
    "Расширение - Code.\n"
    "- Отвечай как code-модель: минимум слов, максимум кода. Одно-два коротких "
    "предложения сути — и сразу рабочий код.\n"
    "- Пиши продакшн-качество: корректно, идиоматично, с обработкой ошибок, "
    "типами и граничными случаями. Никаких заглушек, TODO и псевдокода.\n"
    "- Всегда указывай язык в блоке кода. Показывай импорты и точку входа.\n"
    "- Не извиняйся, не пиши воду, эмодзи, дисклеймеры и вопросы вроде "
    "'хочешь ли ещё'. Если не хватает данных — сделай разумное допущение и "
    "пометь его одной строкой.\n"
    "- Если уместно, добавь короткий пример запуска или вызова."
)

WEB_SEARCH_PROMPT = (
    "Тебе предоставлены свежие результаты веб-поиска по запросу пользователя. "
    "Используй их как источник фактов, опирайся на актуальность этих данных и "
    "указывай источники по названию сайта. Если результаты противоречивы или "
    "недостаточны — прямо скажи об этом."
)

FILES_MODE_PROMPT = (
    "Режим работы с файлами: анализируй прикреплённое содержимое как источник. "
    "Отвечай конкретно по коду или данным из файла, приводи релевантные фрагменты "
    "с пояснениями."
)

_VOICE_TAG_RE = re.compile(
    r"\[(?:joyful|excited|tender|sad|angry|nervous|stern|surprised|contemplative|mundane)\]"
    r"|<(?:laugh|giggle|sigh|gasp|sob|pause|um|gulp|scoff|growl)>"
)


def strip_voice_tags(text: str) -> str:
    """Remove prosody-only tags so stored chat stays clean for reading."""
    cleaned = _VOICE_TAG_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:!?])", r"\1", cleaned)
    return cleaned.strip()


PROVIDER_BY_AI = {
    AiProvider.GROK: "groq",
    AiProvider.OLLAMA: "ollama",
}

ROLE_TO_OPENAI = {
    MessageRole.USER: "user",
    MessageRole.AI: "assistant",
    MessageRole.SYSTEM: "system",
}


@dataclass(slots=True)
class ChatTurn:
    role: MessageRole
    content: str


@dataclass(slots=True)
class Persona:
    system_prompt: str
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    think: bool = False


def build_system_prompt(role: str, character: str | None) -> str:
    role = role.strip()
    character = (character or "").strip()
    if character and character.lower() not in role.lower():
        return f"{role}\n\nCharacter: {character}"
    return role or DEFAULT_SYSTEM_PROMPT


def to_openai_messages(
    system_prompt: str,
    turns: Sequence[ChatTurn],
    *,
    window: int,
) -> list[Message]:
    selected = list(turns)[-window:] if window > 0 else list(turns)
    messages: list[Message] = [{"role": "system", "content": system_prompt}]
    for turn in selected:
        messages.append(
            {"role": ROLE_TO_OPENAI.get(turn.role, "user"), "content": turn.content}
        )
    return messages


class LLMService:
    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings
        self._clients: dict[str, OpenAICompatibleClient] = {
            "groq": GroqClient(
                api_key=(
                    settings.groq_api_key.get_secret_value()
                    if settings.groq_api_key is not None
                    else None
                ),
                model=settings.groq_model,
                base_url=settings.groq_base_url,
                timeout=settings.request_timeout,
            ),
            "ollama": OllamaClient(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
                timeout=settings.request_timeout,
            ),
        }

    def _provider_order(self, preferred: str | None) -> list[str]:
        ordered = [preferred, self._settings.provider, "groq", "ollama"]
        seen: set[str] = set()
        result: list[str] = []
        for provider in ordered:
            if provider and provider not in seen:
                seen.add(provider)
                result.append(provider)
        return result

    async def stream(
        self,
        persona: Persona,
        turns: Sequence[ChatTurn],
    ) -> AsyncIterator[StreamChunk]:
        messages = to_openai_messages(
            persona.system_prompt,
            turns,
            window=self._settings.context_messages,
        )

        errors: list[str] = []
        for provider in self._provider_order(persona.provider):
            client = self._clients.get(provider)
            if client is None or not client.ready:
                continue

            emitted = False
            try:
                async for chunk in client.stream(
                    messages,
                    model=persona.model,
                    temperature=persona.temperature,
                    max_tokens=persona.max_tokens or self._settings.max_tokens,
                    think=persona.think,
                ):
                    emitted = True
                    yield chunk
            except Exception as exc:  # noqa: BLE001 - surface any provider failure
                errors.append(f"{provider}: {exc}")
                if emitted:
                    raise
                continue
            return

        if errors:
            raise LlmUnavailableError("; ".join(errors))
        raise LlmUnavailableError("no provider is configured")

    async def close(self) -> None:
        for client in self._clients.values():
            await client.close()

    async def complete(
        self,
        persona: Persona,
        turns: Sequence[ChatTurn],
    ) -> str:
        parts: list[str] = []
        async for chunk in self.stream(persona, turns):
            if chunk.kind == "content":
                parts.append(chunk.text)
        return "".join(parts).strip()


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    return LLMService(cfg.llm)
