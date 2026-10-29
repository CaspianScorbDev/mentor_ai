# Mentor AI

FastAPI + React (Vite) приложение с долгими стримами (SSE), чатом, веб-поиском, планами/проектами, Помодоро.

## Требования

- Python 3.13+, Poetry 2.4.3
- Node 22+, npm 10+
- PostgreSQL 16 (dev: порт 5433, в Docker: 5432)

## Быстрый старт (локально)

1. Создать `.env` (см. `.env.example` если есть) с конфигом `DATABASE__*`, `LLM__*`, `SEARCH__*`.
2. Установить зависимости бэка: `poetry install`
3. Применить миграции: `alembic upgrade head`
4. Запустить API: `poetry run uvicorn app.backend.server:app --reload --port 8000`
5. Фронт: `cd frontend && npm i && npm run dev` (Vite)

Frontend по умолчанию ходит на `http://localhost:8000` (см. `frontend/src/api.ts`).

Локальный голосовой движок (`kittenml`, тянет torch) ставится группой Poetry `voice`
и ставится обычным `poetry install`. Docker-образ его не содержит (см. ниже).

## Линт/типизация/тесты

- Backend: `poetry run ruff check . && poetry run mypy . && poetry run pytest -q`
- Frontend: `cd frontend && npm run lint && npm run build`

## Docker

```bash
docker compose up --build
```

- API: http://localhost:8000/health
- Frontend: http://localhost:8080
- DB: localhost:5433 (внешний) / db:5432 (внутри сети)

`api` сам применяет миграции при старте (entrypoint → `alembic upgrade head`).
Ollama живёт на хосте: compose прокидывает `LLM__OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`
и `host.docker.internal:host-gateway`. Голос в образе — hosted KittenML (`KITTEN__API_KEY`),
локальный движок в образ не кладётся, чтобы не тащить torch/CUDA.

Nginx фронта проксирует `/api/` → `api:8000` с `proxy_buffering off` (обязателен для SSE). Фронт собирается с `VITE_API_BASE=` (same-origin).

## Стриминг (SSE)

События: `status{detail}`, `sources{items}`, `thinking{content}`, `delta{content}`, `done{message}`, `error{detail,request_id}`. При остановке генерации клиент прерывает запрос — на бэке partial-ответ сохраняется в фоне.
