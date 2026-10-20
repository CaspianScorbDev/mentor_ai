import httpx

from app.core.config import cfg
from app.database.models.ai import AiConfigModel

SUPPORTED_PROVIDERS = ("ollama", "groq")


def groq_ready() -> bool:
    key = cfg.llm.groq_api_key
    return key is not None and bool(key.get_secret_value().strip())


def default_model_for(provider: str) -> str:
    return cfg.llm.groq_model if provider == "groq" else cfg.llm.ollama_model


def effective_provider(config: AiConfigModel | None) -> str:
    provider = (config.provider if config is not None else None) or cfg.llm.provider
    if provider not in SUPPORTED_PROVIDERS:
        provider = cfg.llm.provider
    if provider == "groq" and not groq_ready():
        return "ollama"
    return provider


def effective_model(config: AiConfigModel | None, provider: str) -> str:
    model = (config.model if config is not None else None) or ""
    return model.strip() or default_model_for(provider)


def effective_temperature(config: AiConfigModel | None) -> float:
    if config is not None and config.temperature is not None:
        return config.temperature
    return cfg.llm.temperature


def effective_max_tokens(config: AiConfigModel | None) -> int:
    if config is not None and config.max_tokens is not None:
        return config.max_tokens
    return cfg.llm.max_tokens


def effective_system_prompt(config: AiConfigModel | None) -> str | None:
    prompt = (config.system_prompt if config is not None else None) or ""
    return prompt.strip() or None


async def list_models(provider: str) -> tuple[list[str], str | None]:
    """Return the list of selectable models for a provider (best-effort)."""
    if provider == "ollama":
        return await _list_ollama_models()
    if provider == "groq":
        return await _list_groq_models()
    return [], f"Unknown provider: {provider}"


async def _list_ollama_models() -> tuple[list[str], str | None]:
    base = cfg.llm.ollama_base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base}/api/tags")
    except httpx.HTTPError as exc:
        return [], f"Ollama недоступен: {exc}"
    if response.status_code != 200:
        return [], f"Ollama вернул {response.status_code}"
    payload = response.json()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    names = [
        str(item["name"])
        for item in models
        if isinstance(item, dict) and item.get("name")
    ]
    return names, None


async def _list_groq_models() -> tuple[list[str], str | None]:
    api_key = cfg.llm.groq_api_key
    if api_key is None or not api_key.get_secret_value():
        return [], "Groq API key не задан (LLM__GROQ_API_KEY)"
    url = f"{cfg.llm.groq_base_url.rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                url, headers={"Authorization": f"Bearer {api_key.get_secret_value()}"}
            )
    except httpx.HTTPError as exc:
        return [], f"Groq недоступен: {exc}"
    if response.status_code != 200:
        return [], f"Groq вернул {response.status_code}"
    payload = response.json()
    data = payload.get("data", []) if isinstance(payload, dict) else []
    names = sorted(
        str(item["id"])
        for item in data
        if isinstance(item, dict) and item.get("id")
    )
    return names, None
