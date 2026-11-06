.DEFAULT_GOAL = help
.PHONY: help dev down test lint format typecheck check

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

dev:  ## Start Postgres + app with live reload
	docker compose up --build

down:  ## Stop containers (keeps the database volume)
	docker compose down

test:  ## Run the test suite
	uv run pytest

lint:  ## Check linting and formatting (no changes)
	uv run ruff check src tests
	uv run ruff format --check src tests

format:  ## Auto-fix linting and formatting issues
	uv run ruff check --fix src tests
	uv run ruff format src tests

typecheck:  ## Run static type checking
	uv run mypy

check: lint typecheck test  ## Run all checks in CI
