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
	cd backend && alembic upgrade head

seed:
	cd backend && python -m app.db.seed

demo:
	@echo "demo script lands in M8"
