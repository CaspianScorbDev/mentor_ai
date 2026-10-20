.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install project dependencies via poetry
	poetry install --no-root

lock: ## Refresh poetry.lock
	poetry lock

up: ## Start the stack (db + api) in the background
	docker compose up -d --build

down: ## Stop the stack
	docker compose down

logs: ## Tail stack logs
	docker compose logs -f

build: ## Build the api image
	docker compose build

migrate: ## Apply migrations inside the api container
	docker compose exec api alembic upgrade head

revision: ## Autogenerate a migration (usage: make revision m="message"); needs `make up`
	poetry run alembic revision --autogenerate -m "$(m)"

shell: ## Open a shell inside the api container
	docker compose exec api sh

psql: ## Open psql against the database
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

run: ## Run the api locally (requires a reachable database)
	poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

test: ## Run the test suite (DB tests auto-skip when the database is down)
	poetry run pytest

lint: ## Run ruff
	poetry run ruff check .

format: ## Auto-fix lint issues with ruff
	poetry run ruff check . --fix

typecheck: ## Run mypy
	poetry run mypy .

check: lint typecheck test ## Run all quality gates

.PHONY: help install lock up down logs build migrate revision shell psql run test lint format typecheck check
