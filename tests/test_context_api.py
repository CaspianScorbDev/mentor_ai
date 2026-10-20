from httpx import AsyncClient

from app.database.models.context import UserContextModel
from app.services.context import build_context_block, is_configured

API = "/api/v1"


async def test_context_defaults(client: AsyncClient) -> None:
    await client.patch(f"{API}/context", json={"mentor_mode": True})
    response = await client.get(f"{API}/context")
    assert response.status_code == 200
    body = response.json()
    assert "current_goal" in body
    assert body["mentor_mode"] is True
    assert isinstance(body["configured"], bool)


async def test_context_update_marks_configured(client: AsyncClient) -> None:
    updated = await client.patch(
        f"{API}/context",
        json={
            "user_name": "User",
            "current_goal": "Запустить продукт",
            "specialization": "Продуктовый менеджмент",
            "communication_style": "Кратко и по делу",
            "mentor_tone": "Поддерживающий, но требовательный",
            "language": "Русский",
            "mentor_mode": True,
            "use_schedule": True,
            "use_plans": True,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["current_goal"] == "Запустить продукт"
    assert body["configured"] is True

    cleared = await client.patch(f"{API}/context", json={"current_goal": ""})
    assert cleared.status_code == 200
    assert cleared.json()["current_goal"] == ""


def test_context_block_reflects_values() -> None:
    context = UserContextModel()
    context.user_name = "User"
    context.current_goal = "Стать лучшим ментором"
    context.specialization = "Карьера"
    context.communication_style = "Кратко и по делу"
    context.mentor_tone = "Поддерживающий"
    context.interests = ""
    context.language = "Русский"
    context.mentor_mode = True
    context.use_schedule = True
    context.use_plans = True

    block = build_context_block(context)
    assert "Стать лучшим ментором" in block
    assert "Карьера" in block
    assert "mentor" in block.lower()
    assert is_configured(context) is True
