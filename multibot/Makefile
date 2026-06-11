.PHONY: install dev test lint format migrate worker docker-up docker-down

install:
	uv sync --extra dev

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -v --tb=short

lint:
	uv run ruff check app/ tests/

format:
	uv run ruff format app/ tests/

migrate:
	uv run alembic upgrade head

worker:
	uv run python -m arq workers.main.WorkerSettings

docker-up:
	docker compose up -d

docker-down:
	docker compose down
