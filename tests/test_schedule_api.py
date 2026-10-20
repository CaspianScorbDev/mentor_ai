from httpx import AsyncClient

API = "/api/v1"
ENDPOINT = f"{API}/schedule/events"


async def test_schedule_event_lifecycle(client: AsyncClient) -> None:
    created = await client.post(
        ENDPOINT,
        json={
            "title": "Standup",
            "date": "2026-10-20",
            "start": 540,
            "duration": 30,
            "category": "work",
            "detail": "daily sync",
        },
    )
    assert created.status_code == 201
    event = created.json()
    assert event["date"] == "2026-10-20"
    assert event["start"] == 540
    assert event["duration"] == 30
    event_id = event["id"]

    listed = await client.get(
        ENDPOINT, params={"start": "2026-10-20", "end": "2026-10-20"}
    )
    assert listed.status_code == 200
    assert any(item["id"] == event_id for item in listed.json())

    patched = await client.patch(
        f"{ENDPOINT}/{event_id}", json={"start": 600, "category": "aida"}
    )
    assert patched.status_code == 200
    assert patched.json()["start"] == 600
    assert patched.json()["category"] == "aida"

    deleted = await client.delete(f"{ENDPOINT}/{event_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"{ENDPOINT}/{event_id}")
    assert missing.status_code == 404


async def test_schedule_event_validation(client: AsyncClient) -> None:
    response = await client.post(
        ENDPOINT,
        json={"title": "Bad", "date": "2026-10-20", "start": 1500, "duration": 0},
    )
    assert response.status_code == 422
