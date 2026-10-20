import app.database.models  # noqa: F401  (side effect: registers models)
from app.database.base import Base

EXPECTED_TABLES = {"ai_system", "chats", "messages", "users"}


def test_all_models_are_registered_on_metadata() -> None:
    assert EXPECTED_TABLES <= set(Base.metadata.tables)
