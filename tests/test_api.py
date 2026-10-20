from httpx import AsyncClient

API = "/api/v1"


async def test_health(client: AsyncClient) -> None:
    response = await client.get(f"{API}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_create_and_get_ai(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/ai",
        json={
            "provider": "grok",
            "model": "openai/gpt-oss-120b",
            "name": "Aida",
            "role": "You are a mentor",
            "character": "warm",
            "temperature": 0.5,
        },
    )
    assert response.status_code == 201
    ai = response.json()
    assert ai["provider"] == "grok"

    fetched = await client.get(f"{API}/ai/{ai['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Aida"


async def test_ai_not_found(client: AsyncClient) -> None:
    response = await client.get(f"{API}/ai/999999")
    assert response.status_code == 404


async def test_chat_lifecycle_and_streaming(client: AsyncClient) -> None:
    created = await client.post(
        f"{API}/chats", json={"message": "First question", "title": "Onboarding"}
    )
    assert created.status_code == 201
    chat = created.json()
    chat_id = chat["id"]
    assert chat["title"] == "Onboarding"
    assert len(chat["messages"]) == 1
    assert chat["messages"][0]["role"] == "user"

    listed = await client.get(f"{API}/chats")
    assert listed.status_code == 200
    assert any(item["id"] == chat_id for item in listed.json())

    streamed = await client.post(
        f"{API}/chats/{chat_id}/messages", json={"content": "Tell me more"}
    )
    assert streamed.status_code == 200
    assert '"type": "delta"' in streamed.text
    assert '"type": "done"' in streamed.text

    detail = await client.get(f"{API}/chats/{chat_id}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert messages[-1]["role"] == "ai"
    assert messages[-1]["content"] == "Hello!"

    deleted = await client.delete(f"{API}/chats/{chat_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"{API}/chats/{chat_id}")
    assert missing.status_code == 404
