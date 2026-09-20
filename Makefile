.PHONY: help install run run-prod makemigration migrate rollback current history test format lint lint-fix clean

.DEFAULT_GOAL := help

help:
	@echo "install          - uv sync (installs deps + dev group)"
	@echo "run              - run the dev server with autoreload"
	@echo "run-prod         - run the server without autoreload"
	@echo "makemigration    - generate a migration (name=\"add users table\")"
	@echo "migrate          - apply all migrations"
	@echo "rollback         - roll back the last migration"
	@echo "current          - show the current DB revision"
	@echo "history          - show migration history"
	@echo "test             - run the test suite (args=\"-k test_auth\")"
	@echo "format           - format code and sort imports (ruff)"
	@echo "lint             - check for lint errors (ruff)"
	@echo "lint-fix         - auto-fix what ruff can fix safely"
	@echo "clean            - remove __pycache__ and .pyc files"

install:
	@uv sync

run:
	@uv run --directory src uvicorn main:app --reload

run-prod:
	@uv run --directory src uvicorn main:app --host 0.0.0.0 --port 8000

makemigration:
	@uv run alembic revision --autogenerate -m "$(name)"

migrate:
	@uv run alembic upgrade head

rollback:
	@uv run alembic downgrade -1

current:
	@uv run alembic current

history:
	@uv run alembic history

test:
	@uv run pytest -v $(args)

format:
	@uv run ruff format .
	@uv run ruff check . --fix --select I

lint:
	@uv run ruff check .

lint-fix:
	@uv run ruff check . --fix

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.py[co]" -delete
