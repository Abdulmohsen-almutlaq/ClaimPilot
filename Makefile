.PHONY: install dev lint typecheck test migrate seed demo

install:
	cd backend && pip install -e ".[dev]"

dev:
	cd backend && uvicorn app.main:app --reload

lint:
	cd backend && ruff check .

typecheck:
	cd backend && mypy app

test:
	cd backend && pytest

migrate:
	@echo "alembic migrations land in M2"

seed:
	@echo "seed data lands in M2"

demo:
	@echo "demo script lands in M8"
