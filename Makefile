PYTHON ?= python3.11
VENV ?= .venv

.PHONY: install test lint format migrate run bootstrap smoke

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

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
	@if [ ! -f .env ]; then cp .env.example .env; fi
	$(VENV)/bin/python -m keynetra.cli migrate --confirm-destructive
	$(VENV)/bin/python -m keynetra.cli config doctor
	$(VENV)/bin/python -m pytest -q tests/test_api_contract.py tests/test_compiled_policies.py

smoke:
	$(PYTHON) -m pytest -q tests/test_api_contract.py tests/test_compiled_policies.py tests/test_doctor.py
