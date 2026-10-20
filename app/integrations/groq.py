import os

from app.integrations.base import OpenAICompatibleClient

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqClient(OpenAICompatibleClient):
    """Groq chat API (OpenAI-compatible)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
    ) -> None:
        super().__init__(
            base_url=base_url,
            api_key=api_key or os.environ.get("GROQ_API_KEY"),
            model=model,
            timeout=timeout,
        )
