from httpx import AsyncClient

API = "/api/v1"


async def test_ai_config_defaults(client: AsyncClient) -> None:
    response = await client.get(f"{API}/ai/config")
    assert response.status_code == 200
    body = response.json()
    assert body["effective_provider"] in {"groq", "ollama"}
    assert body["effective_model"]
    assert body["effective_temperature"] >= 0
    assert body["effective_max_tokens"] >= 1


async def test_ai_config_all_fields_optional(client: AsyncClient) -> None:
    response = await client.patch(f"{API}/ai/config", json={})
    assert response.status_code == 200
    assert "effective_provider" in response.json()


async def test_ai_config_update_and_clear(client: AsyncClient) -> None:
    updated = await client.patch(
        f"{API}/ai/config", json={"temperature": 0.3, "provider": "ollama"}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["temperature"] == 0.3
    assert body["effective_temperature"] == 0.3
    assert body["effective_provider"] == "ollama"

    cleared = await client.patch(f"{API}/ai/config", json={"temperature": None, "provider": None})
    assert cleared.status_code == 200
    reset = cleared.json()
    assert reset["temperature"] is None
    assert reset["provider"] is None


async def test_ai_config_rejects_invalid_temperature(client: AsyncClient) -> None:
    response = await client.patch(f"{API}/ai/config", json={"temperature": 5})
    assert response.status_code == 422
