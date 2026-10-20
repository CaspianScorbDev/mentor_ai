import os
import ssl
from functools import lru_cache
from ipaddress import ip_network
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_ENV_VAR = "ENV_FILE"
CRT_EXTENSIONS = {".crt", ".pem", ".cer", ".der"}


def resolve_env_file() -> Path:
    return Path(os.environ.get(ENV_FILE_ENV_VAR, ".env"))


ENV_FILE = resolve_env_file()


class ApplicationSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    name: str = Field(
        ...,
        min_length=4,
        max_length=100,
        description="Application name",
    )

    version: str = Field(
        ...,
        pattern=r"^\d+\.\d+\.\d+([\-+].+)?$",
        description="Application version in semver format",
    )

    environment: Literal["production", "staging", "test", "development"] = Field(
        ...,
        description="Runtime environment",
    )

    debug: bool = Field(default=False, description="Enable debug mode")
    docs: str | None = Field(default=None, description="Enable docs_url")
    redoc: str | None = Field(default=None, description="Enable redoc_url")

    secret_key: SecretStr = Field(
        ...,
        min_length=32,
        description="Application secret key (min 32 chars)",
    )

    timezone: str = Field(
        default="UTC",
        description="Application timezone (IANA, e.g. Europe/Moscow)",
    )

    api_prefix: str = Field(
        ...,
        pattern=r"^/",
        description="API prefix, must start with /",
    )

    host: str = Field(
        default="0.0.0.0",
        description="Host the application binds to",
    )

    port: int = Field(
        default=8000,
        description="Application port",
    )

    workers: int = Field(
        ...,
        ge=1,
        le=64,
        description="Number of worker processes",
    )

    reload: bool = Field(
        ...,
        description="Auto-reload on code changes (dev only)",
    )

    allowed_hosts: list[str] = Field(
        ...,
        description="List of allowed hosts",
    )

    allowed_origins: list[str] = Field(
        ...,
        description="List of allowed CORS origins",
    )

    trusted_proxies: list[str] = Field(
        default_factory=list,
        description="List of trusted proxies (CIDR or IP)",
    )

    api_key: SecretStr | None = Field(
        default=None,
        description="When set, every API request must send this value in the X-API-Key header",
    )

    rate_limit_per_minute: int = Field(
        default=0,
        ge=0,
        le=1_000_000,
        description="Per-client request budget per minute; 0 disables the limiter",
    )

    rate_limit_burst: int = Field(
        default=0,
        ge=0,
        le=1_000_000,
        description="Extra burst allowance on top of rate_limit_per_minute",
    )

    log_json: bool = Field(
        default=False,
        description="Emit structured JSON logs instead of human-readable lines",
    )

    @field_validator("name", "api_prefix")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("docs", "redoc", mode="before")
    @classmethod
    def _validate_docs(cls, v: object, info: ValidationInfo) -> str | None:
        default_path = f"/{info.field_name}"

        if v is None or v == "" or v is False:
            return None

        if v is True:
            return default_path

        if not isinstance(v, str):
            raise ValueError(f"{info.field_name}: expected str | None, got {type(v).__name__}")

        v = v.strip()

        lowered = v.lower()
        if lowered in ("false", "0", "no", "off"):
            return None
        if lowered in ("true", "1", "yes", "on"):
            return default_path

        if v in ("development", "test"):
            return default_path

        if v.startswith("/") and len(v) > 1:
            return v

        raise ValueError(
            f"{info.field_name}: cannot interpret {v!r}; "
            "expected None, true/false, an env name, or a path starting with '/'"
        )

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
            raise ValueError(f"Unknown timezone: {v!r}") from exc
        return v

    @field_validator("api_prefix")
    @classmethod
    def _normalize_prefix(cls, v: str) -> str:
        return v.rstrip("/") or "/"

    @field_validator("allowed_hosts")
    @classmethod
    def _validate_hosts(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("list must not be empty")
        for host in v:
            if any(ch in host for ch in " \t\r\n/\\"):
                raise ValueError(f"allowed_hosts entry must be a bare hostname, got {host!r}")
        return v

    @field_validator("allowed_origins")
    @classmethod
    def _validate_origins(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("list must not be empty")
        for origin in v:
            parts = urlsplit(origin)
            if parts.scheme not in ("http", "https"):
                raise ValueError(
                    f"allowed_origins entry must start with http:// or https://, got {origin!r}"
                )
            if not parts.netloc:
                raise ValueError(f"allowed_origins entry has no host: {origin!r}")
            if parts.path or parts.query or parts.fragment:
                raise ValueError(
                    f"allowed_origins entry must not contain path/query/fragment: {origin!r}"
                )
        return v

    @field_validator("trusted_proxies")
    @classmethod
    def _validate_proxies(cls, v: list[str]) -> list[str]:
        for proxy in v:
            try:
                ip_network(proxy, strict=False)
            except ValueError:
                raise ValueError(
                    f"trusted_proxies entry must be an IP or CIDR, got {proxy!r}"
                ) from None
        return v

    @model_validator(mode="after")
    def _check_runtime(self) -> "ApplicationSettings":
        if self.environment in ("production", "staging"):
            if self.debug:
                raise ValueError("debug must be False when environment is not development")
            if self.reload:
                raise ValueError("reload must be False when environment is not development")
        if self.environment == "production":
            for origin in self.allowed_origins:
                if urlsplit(origin).scheme != "https":
                    raise ValueError(
                        f"allowed_origins must use https in production, got {origin!r}"
                    )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def allows_dev_secrets(self) -> bool:
        """Заглушки `dev-only-*` допустимы в development и test, не в бою."""
        return self.environment in ("development", "test")


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    host: str = Field(..., min_length=1, description="PostgreSQL host")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port")
    user: str = Field(..., min_length=1, description="PostgreSQL user")
    password: SecretStr = Field(..., min_length=1, description="PostgreSQL password")
    name: str = Field(..., min_length=1, description="PostgreSQL database name")
    pool_size: int = Field(..., ge=1, le=1000, description="Connection pool size")
    max_overflow: int = Field(..., ge=0, le=1000, description="Maximum pool overflow")
    pool_timeout: int = Field(..., ge=1, le=600, description="Pool acquisition timeout, sec")
    pool_recycle: int = Field(
        ..., ge=-1, le=86400, description="Recycle connections, sec (-1 disables)"
    )
    pre_ping: bool = Field(default=True, description="Check connection")
    echo: bool = Field(..., description="Log SQL queries")
    ssl_mode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] = Field(
        ..., description="SSL mode for PostgreSQL connection"
    )
    version: str = Field(
        default="postgres:17-bookworm",
        description="Docker image tag used for the database service",
    )

    ssl_ca: str | None = Field(
        default=None,
        description="Path to CA certificate (required for verify-ca/verify-full)",
    )

    @field_validator("ssl_ca")
    @classmethod
    def _check_ssl_ca(cls, v: str | None) -> str | None:
        if v is not None and Path(v).suffix.lower() not in CRT_EXTENSIONS:
            raise ValueError(
                "ssl_ca must point to a certificate file "
                f"with one of extensions: {sorted(CRT_EXTENSIONS)}"
            )
        return v

    @model_validator(mode="after")
    def _check_ssl(self) -> "DatabaseSettings":
        if self.ssl_mode in ("verify-ca", "verify-full") and not self.ssl_ca:
            raise ValueError(f"ssl_mode={self.ssl_mode!r} requires ssl_ca to be set")
        if self.ssl_mode in ("disable", "allow", "prefer", "require") and self.ssl_ca is not None:
            raise ValueError(f"ssl_mode={self.ssl_mode!r} does not use ssl_ca; remove it")
        return self

    @property
    def database_dsn(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"

    @property
    def connect_args(self) -> dict[str, Any]:
        if self.ssl_mode in ("disable", "allow", "prefer"):
            return {"ssl": self.ssl_mode}
        context = ssl.create_default_context(cafile=self.ssl_ca)
        if self.ssl_mode == "require":
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        elif self.ssl_mode == "verify-ca":
            context.check_hostname = False
        return {"ssl": context}


class BotSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    token: SecretStr = Field(..., min_length=20)
    type: Literal["polling", "webhook"] = Field(
        default="polling", description="Transport used to receive updates"
    )
    url_webhook: str | None = Field(
        default=None, description="Public webhook URL, required when type=webhook"
    )
    admin_ids: list[int] = Field(
        default_factory=list, description="Telegram user IDs allowed to administer"
    )
    logging_chat_id: int | None = Field(
        default=None, description="Chat ID for service log messages"
    )
    notifications_chat_id: int | None = Field(
        default=None, description="Chat ID for user notifications"
    )
    webhook_secret: SecretStr | None = Field(
        default=None, description="Secret token Telegram sends in X-Telegram-Bot-Api-Secret-Token"
    )

    @field_validator("admin_ids", mode="before")
    @classmethod
    def _coerce_id_list(cls, v: object) -> object:
        if isinstance(v, str):
            text = v.strip().strip("[]")
            if not text:
                return []
            return [int(part) for part in text.split(",") if part.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("logging_chat_id", "notifications_chat_id", mode="before")
    @classmethod
    def _coerce_single_id(cls, v: object) -> object:
        if isinstance(v, str):
            text = v.strip()
            if not text:
                return None
            return int(text)
        return v

    @field_validator("admin_ids")
    @classmethod
    def _check_ids(cls, v: list[int]) -> list[int]:
        if any(chat_id == 0 for chat_id in v):
            raise ValueError("telegram chat id must not be 0")
        if len(set(v)) != len(v):
            raise ValueError("admin_ids must not contain duplicates")
        return v

    @model_validator(mode="after")
    def _check_transport(self) -> "BotSettings":
        if self.type == "webhook":
            if not self.url_webhook:
                raise ValueError("url_webhook is required when type=webhook")
            if not self.url_webhook.startswith("https://"):
                raise ValueError("url_webhook must use https")
            if self.webhook_secret is None:
                raise ValueError("webhook_secret is required when type=webhook")
        return self


class LlmSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    provider: Literal["groq", "ollama"] = Field(
        default="groq", description="Primary LLM provider"
    )
    request_timeout: float = Field(
        default=60.0, ge=1.0, le=600.0, description="Per-request timeout, sec"
    )
    context_messages: int = Field(
        default=20, ge=2, le=200, description="Sliding window size (messages kept in context)"
    )
    max_tokens: int = Field(
        default=1024, ge=1, le=32768, description="Max tokens generated per reply"
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0, description="Default sampling temperature"
    )

    groq_api_key: SecretStr | None = Field(default=None, description="Groq API key")
    groq_base_url: str = Field(
        default="https://api.groq.com/openai/v1", description="Groq API base URL"
    )
    groq_model: str = Field(default="openai/gpt-oss-120b", description="Groq model name")

    ollama_base_url: str = Field(
        default="http://localhost:11434/v1", description="Ollama OpenAI-compatible base URL"
    )
    ollama_model: str = Field(default="qwen2.5:3b", description="Ollama model name")

    @field_validator("groq_base_url", "ollama_base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"base URL must be a valid http(s) URL, got {v!r}")
        return v.rstrip("/")


class KittenSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    backend: Literal["auto", "local", "hosted"] = Field(
        default="auto",
        description=(
            "Voice engine: 'auto' picks hosted when an API key is set, else local; "
            "'local' runs the KittenTTS2 package; 'hosted' calls the KittenML API"
        ),
    )
    api_key: SecretStr | None = Field(
        default=None, description="KittenML API key (hosted backend only)"
    )
    base_url: str = Field(
        default="https://api.kittenml.com/v1", description="KittenML API base URL (hosted)"
    )
    model: str = Field(default="kitten-tts-2-latest", description="Hosted model id")
    local_repo: str = Field(
        default="KittenML/kitten-tts-2", description="Local Hugging Face repo or directory"
    )
    device: Literal["auto", "cpu", "mps", "cuda"] = Field(
        default="auto", description="Torch device for the local backend"
    )
    voice: str | None = Field(default=None, description="Default built-in voice name")
    reference: str | None = Field(
        default=None, description="Path to a reference clip for voice cloning"
    )
    stt_model: str = Field(
        default="openai/whisper-small", description="Local transcription model"
    )
    stt_language: str = Field(default="ru", description="Transcription language hint")
    sample_rate: int = Field(default=24000, ge=8000, le=48000, description="Output sample rate")
    request_timeout: float = Field(
        default=180.0, ge=5.0, le=900.0, description="Voice request timeout, sec"
    )
    max_input_chars: int = Field(
        default=4000, ge=1, le=40000, description="Max characters per synthesis request"
    )
    voices_dir: str = Field(default="data/voices", description="Where cloned voice clips live")

    @field_validator("base_url")
    @classmethod
    def _validate_base_url(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"base URL must be a valid http(s) URL, got {v!r}")
        return v.rstrip("/")

    @field_validator("reference", mode="before")
    @classmethod
    def _blank_to_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @property
    def has_api_key(self) -> bool:
        if self.api_key is None:
            return False
        return self.api_key.get_secret_value().strip().startswith("sk_")

    @property
    def resolved_backend(self) -> Literal["local", "hosted"]:
        if self.backend == "auto":
            return "hosted" if self.has_api_key else "local"
        return self.backend

    @property
    def ready(self) -> bool:
        if self.resolved_backend == "hosted":
            return self.has_api_key
        return True


class MailSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    host: str = Field(
        default="",
        description="SMTP host; leave empty to disable email delivery entirely",
    )
    port: int = Field(default=587, ge=1, le=65535, description="SMTP port")
    username: str = Field(default="", description="SMTP username (optional)")
    password: SecretStr | None = Field(default=None, description="SMTP password")
    from_address: str = Field(default="", description="Sender address (From header)")
    use_tls: bool = Field(default=True, description="Upgrade the connection with STARTTLS")
    timeout: float = Field(default=20.0, ge=1.0, le=300.0, description="SMTP timeout, sec")

    @field_validator("host", "from_address", "username")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("from_address", mode="after")
    @classmethod
    def _check_from(cls, v: str, info: ValidationInfo) -> str:
        host = info.data.get("host", "")
        if host and v and "@" not in v:
            raise ValueError("from_address must be a valid email address")
        return v

    @property
    def ready(self) -> bool:
        return bool(self.host and self.from_address)


class WebSearchSettings(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    provider: Literal["auto", "duckduckgo", "brave", "searxng"] = Field(
        default="auto",
        description="Search backend: auto picks Brave/SearXNG when configured, else DuckDuckGo",
    )
    brave_api_key: SecretStr | None = Field(
        default=None, description="Brave Search API key (enables the brave provider)"
    )
    brave_base_url: str = Field(
        default="https://api.search.brave.com/res/v1/web/search",
        description="Brave Search endpoint",
    )
    searxng_url: str | None = Field(
        default=None, description="Base URL of a SearXNG instance, e.g. https://searx.example.com"
    )
    timeout: float = Field(default=8.0, ge=1.0, le=60.0, description="Search request timeout, sec")
    max_results: int = Field(default=5, ge=1, le=20, description="Results requested per query")
    read_pages: int = Field(
        default=3, ge=0, le=10, description="How many top pages to fetch for full text"
    )
    page_timeout: float = Field(
        default=6.0, ge=1.0, le=60.0, description="Per-page fetch timeout, sec"
    )
    max_page_chars: int = Field(
        default=1800, ge=200, le=20000, description="Max characters kept per fetched page"
    )
    max_concurrency: int = Field(
        default=4, ge=1, le=32, description="Max simultaneous page fetches"
    )

    @field_validator("brave_base_url")
    @classmethod
    def _validate_brave_url(cls, v: str) -> str:
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"brave_base_url must be a valid http(s) URL, got {v!r}")
        return v.rstrip("/")

    @field_validator("searxng_url")
    @classmethod
    def _validate_searxng_url(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        value = v.strip()
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError(f"searxng_url must be a valid http(s) URL, got {value!r}")
        return value.rstrip("/")

    @property
    def has_brave(self) -> bool:
        return self.brave_api_key is not None and bool(
            self.brave_api_key.get_secret_value().strip()
        )


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_ignore_empty=False,
        case_sensitive=False,
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
        validate_default=True,
    )

    application: ApplicationSettings
    database: DatabaseSettings
    bot: BotSettings
    llm: LlmSettings = Field(default_factory=LlmSettings)
    mail: MailSettings = Field(default_factory=MailSettings)
    kitten: KittenSettings = Field(default_factory=KittenSettings)
    search: WebSearchSettings = Field(default_factory=WebSearchSettings)


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


cfg = get_config()

__all__ = [
    "Config",
    "ApplicationSettings",
    "DatabaseSettings",
    "BotSettings",
    "KittenSettings",
    "LlmSettings",
    "MailSettings",
    "WebSearchSettings",
    "get_config",
    "cfg",
]
