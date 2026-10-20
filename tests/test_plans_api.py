from httpx import AsyncClient

API = "/api/v1"


async def test_plan_goal(client: AsyncClient) -> None:
    fetched = await client.get(f"{API}/plans/goal")
    assert fetched.status_code == 200
    assert fetched.json()["title"]

    updated = await client.patch(
        f"{API}/plans/goal", json={"title": "Запуск продукта", "description": "К осени"}
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Запуск продукта"
    assert body["description"] == "К осени"


async def test_projects_seeded_and_managed(client: AsyncClient) -> None:
    listed = await client.get(f"{API}/plans/projects")
    assert listed.status_code == 200
    assert len(listed.json()) >= 1

    created = await client.post(
        f"{API}/plans/projects", json={"title": "Пет-проект", "description": "Для души"}
    )
    assert created.status_code == 201
    project = created.json()
    assert project["title"] == "Пет-проект"
    project_id = project["id"]
    assert any(item["id"] == project_id for item in listed.json()) is False

    updated = await client.patch(
        f"{API}/plans/projects/{project_id}", json={"title": "Пет-проект v2"}
    )
    assert updated.json()["title"] == "Пет-проект v2"

    task = await client.post(
        f"{API}/plans/tasks",
        json={
            "title": "Задача проекта",
            "stage": "ideas",
            "category": "work",
            "goal_id": project_id,
        },
    )
    assert task.json()["goal_id"] == project_id

    assert (await client.delete(f"{API}/plans/projects/{project_id}")).status_code == 204
    assert (await client.get(f"{API}/plans/tasks/{task.json()['id']}")).status_code == 404


async def test_plan_task_and_subtasks(client: AsyncClient) -> None:
    created = await client.post(
        f"{API}/plans/tasks",
        json={
            "title": "Собрать прототип",
            "stage": "progress",
            "category": "aida",
            "deadline": "2 дня",
            "assignee": "Aida",
        },
    )
    assert created.status_code == 201
    task = created.json()
    assert task["stage"] == "progress"
    assert task["subtasks"] == []
    task_id = task["id"]

    with_sub = await client.post(
        f"{API}/plans/tasks/{task_id}/subtasks", json={"title": "Шаг один"}
    )
    assert with_sub.status_code == 201
    subtasks = with_sub.json()["subtasks"]
    assert len(subtasks) == 1
    subtask_id = subtasks[0]["id"]

    checked = await client.patch(
        f"{API}/plans/subtasks/{subtask_id}", json={"done": True}
    )
    assert checked.status_code == 200
    assert checked.json()["done"] is True

    moved = await client.patch(f"{API}/plans/tasks/{task_id}", json={"stage": "done"})
    assert moved.json()["stage"] == "done"

    assert (await client.delete(f"{API}/plans/tasks/{task_id}")).status_code == 204
    assert (await client.get(f"{API}/plans/tasks/{task_id}")).status_code == 404
