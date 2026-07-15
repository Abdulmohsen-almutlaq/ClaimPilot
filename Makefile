.PHONY: install dev lint typecheck test migrate seed demo evals evals-smoke evals-gate

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
	cd backend && python -m app.db.seed && python -m app.rag.ingest

evals: # full live eval run (needs docker stack + provider key); commit results.json after
	python evals/run_evals.py --gate

evals-smoke: # stratified 15-case subset for quick checks
	python evals/run_evals.py --smoke --gate

evals-gate: # CI gate: verifies committed results.json against thresholds (no LLM calls)
	pytest evals/test_evals.py -q

demo:
	@echo "demo script lands in M8"
