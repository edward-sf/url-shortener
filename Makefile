.DEFAULT_GOAL = help
.PHONY: help dev down migrate test test-db lint format typecheck check

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

dev:  ## Start Postgres + app with live reload
	docker compose up --build

down:  ## Stop containers (keeps the database volume)
	docker compose down

migrate:  ## Apply database migrations to the dev database
	uv run alembic upgrade head

test:  ## Run the test suite
	uv run pytest

test-db:  ## Create the test database (run once per Docker volume)
	docker compose exec db createdb -U shortener shortener_test

lint:  ## Check linting and formatting (no changes)
	uv run ruff check src tests migrations
	uv run ruff format --check src tests migrations

format:  ## Auto-fix linting and formatting issues
	uv run ruff check --fix src tests migrations
	uv run ruff format src tests migrations

typecheck:  ## Run static type checking
	uv run mypy

check: lint typecheck test  ## Run all checks in CI
