.PHONY: install dev backend frontend frontend-install frontend-build test eval fixtures kb macros eval-classifier eval-retrieval eval-drafting

install:
	uv sync

# Run backend (:8000) and frontend (:5173) concurrently via the Python launcher.
# Ctrl-C stops both. The launcher works without `make` — useful in shells that
# don't have GNU make.
dev:
	uv run python -m scripts.dev

backend:
	uv run uvicorn app.main:app --reload --port 8000

frontend:
	pnpm --dir frontend dev

frontend-install:
	pnpm --dir frontend install

frontend-build:
	pnpm --dir frontend build

test:
	uv run pytest

eval:
	uv run pytest tests/eval -m "ragas"

fixtures:
	uv run python -m scripts.generate_synthetic_fixtures

kb:
	uv run python -m scripts.generate_kb

macros:
	uv run python -m scripts.generate_macros

eval-classifier:
	uv run python -m scripts.eval_classifier

eval-retrieval:
	uv run python -m scripts.eval_retrieval

eval-drafting:
	uv run python -m scripts.eval_drafting
