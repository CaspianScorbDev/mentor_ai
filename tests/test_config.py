import pytest
from pydantic import ValidationError

from app.core.config import ApplicationSettings, BotSettings, DatabaseSettings, LlmSettings


def make_application(**overrides: object) -> ApplicationSettings:
    data: dict[str, object] = {
        "name": "mentor-ai",
        "version": "1.0.0",
        "environment": "development",
        "secret_key": "x" * 40,
        "api_prefix": "/api/v1",
        "workers": 1,
        "reload": True,
        "allowed_hosts": ["localhost"],
        "allowed_origins": ["http://localhost:3000"],
        "docs": "/docs",
        "redoc": "/redoc",
    }
    data.update(overrides)
    return ApplicationSettings(**data)


def make_database(**overrides: object) -> DatabaseSettings:
    data: dict[str, object] = {
        "host": "localhost",
        "user": "mentor",
        "password": "secret",
        "name": "mentor_ai",
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 30,
        "pool_recycle": 1800,
        "echo": False,
        "ssl_mode": "disable",
    }
    data.update(overrides)
    return DatabaseSettings(**data)


def test_docs_false_disables_urls() -> None:
    settings = make_application(docs=False, redoc=False)
    assert settings.docs is None
    assert settings.redoc is None


def test_docs_true_uses_default_path() -> None:
    settings = make_application(docs=True, redoc=True)
    assert settings.docs == "/docs"
    assert settings.redoc == "/redoc"


def test_api_prefix_is_normalized() -> None:
    assert make_application(api_prefix="/api/v1/").api_prefix == "/api/v1"


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_application(timezone="Mars/Phobos")


def test_production_forbids_debug_and_reload() -> None:
    with pytest.raises(ValidationError):
        make_application(environment="production", debug=True, reload=False)
    with pytest.raises(ValidationError):
        make_application(environment="production", debug=False, reload=True)


def test_production_requires_https_origins() -> None:
    with pytest.raises(ValidationError):
        make_application(
            environment="production",
            debug=False,
            reload=False,
            allowed_origins=["http://example.com"],
        )


def test_origin_with_path_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_application(allowed_origins=["http://example.com/api"])


def test_ssl_requires_ca_for_verify_modes() -> None:
    with pytest.raises(ValidationError):
        make_database(ssl_mode="verify-full")


def test_ssl_ca_rejected_for_insecure_modes() -> None:
    with pytest.raises(ValidationError):
        make_database(ssl_mode="disable", ssl_ca="/tmp/ca.pem")


def test_database_dsn_is_quoted() -> None:
    settings = make_database(password="p@ss word")
    assert "p%40ss%20word" in settings.database_dsn


def test_webhook_requires_url_and_secret() -> None:
    with pytest.raises(ValidationError):
        BotSettings(token="t" * 20, type="webhook")


def test_webhook_with_url_but_no_secret_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BotSettings(token="t" * 20, type="webhook", url_webhook="https://example.com/hook")


def test_webhook_valid_config() -> None:
    settings = BotSettings(
        token="t" * 20,
        type="webhook",
        url_webhook="https://example.com/hook",
        webhook_secret="s" * 10,
    )
    assert settings.type == "webhook"


def test_admin_ids_duplicates_rejected() -> None:
    with pytest.raises(ValidationError):
        BotSettings(token="t" * 20, admin_ids=[1, 1])


def test_admin_ids_parsed_from_string() -> None:
    settings = BotSettings(token="t" * 20, admin_ids="1,2,3")
    assert settings.admin_ids == [1, 2, 3]


def test_llm_base_url_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        LlmSettings(ollama_base_url="not-a-url")


def test_llm_defaults() -> None:
    settings = LlmSettings()
    assert settings.provider == "groq"
    assert settings.groq_base_url == "https://api.groq.com/openai/v1"
    assert settings.groq_api_key is None
