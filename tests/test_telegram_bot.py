from app.database.models.chat import MessageRole
from app.services import telegram_bot as bot_module
from app.services.llm import ChatTurn


def _runner(monkeypatch) -> tuple[bot_module.TelegramBotRunner, list[tuple[int, str]]]:
    runner = bot_module.TelegramBotRunner()
    sent: list[tuple[int, str]] = []

    async def fake_remember(_chat_id: int) -> None:
        return None

    async def fake_reply(chat_id: int, text: str) -> None:
        sent.append((chat_id, text))

    monkeypatch.setattr(runner, "_remember_chat", fake_remember)
    monkeypatch.setattr(runner, "_reply", fake_reply)
    return runner, sent


async def test_help_lists_commands(monkeypatch) -> None:
    runner, sent = _runner(monkeypatch)
    await runner._handle(321, "/help")
    assert sent and sent[0][0] == 321
    assert "/today" in sent[0][1]
    assert "/digest" in sent[0][1]


async def test_id_returns_chat_id(monkeypatch) -> None:
    runner, sent = _runner(monkeypatch)
    await runner._handle(555, "/id")
    assert "555" in sent[0][1]


async def test_reset_clears_history(monkeypatch) -> None:
    runner, sent = _runner(monkeypatch)
    runner._history[900] = [ChatTurn(role=MessageRole.USER, content="hi")]
    await runner._handle(900, "/reset")
    assert 900 not in runner._history
    assert "очищен" in sent[0][1].lower()


async def test_command_with_bot_suffix_is_routed(monkeypatch) -> None:
    runner, sent = _runner(monkeypatch)
    await runner._handle(777, "/id@aidaMentorBot")
    assert "777" in sent[0][1]


async def test_extract_message_parses_update() -> None:
    update = {"update_id": 1, "message": {"chat": {"id": 5}, "text": "  привет  "}}
    assert bot_module._extract_message(update) == (5, "привет")
    assert bot_module._extract_message({"update_id": 2}) is None
