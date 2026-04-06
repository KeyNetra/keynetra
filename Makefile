PYTHON ?= python3.11

.PHONY: install test lint format migrate run

install:
	$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check-only .

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

migrate:
	$(PYTHON) -m keynetra.cli migrate --confirm-destructive

run:
	$(PYTHON) -m uvicorn keynetra.api.main:app --host 0.0.0.0 --port 8000
