PYTHON ?= python3.11
VENV ?= .venv

.PHONY: install test lint format migrate run bootstrap smoke

install:
	@if [ -f requirements.lock ] && [ -f requirements-dev.lock ]; then \
		$(PYTHON) -m pip install -r requirements-dev.lock; \
	else \
		$(PYTHON) -m pip install -r requirements.txt -r requirements-dev.txt; \
	fi

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check-only .
	lint-imports --config .importlinter

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

migrate:
	keynetra migrate --confirm-destructive

run:
	$(PYTHON) -m uvicorn keynetra.api.main:app --host 0.0.0.0 --port 8000

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	@if [ -f requirements.lock ] && [ -f requirements-dev.lock ]; then \
		$(VENV)/bin/python -m pip install -r requirements-dev.lock; \
	else \
		$(VENV)/bin/python -m pip install -r requirements.txt -r requirements-dev.txt; \
	fi
	$(VENV)/bin/python -m pip install -e .
	@if [ ! -f .env ]; then cp .env.example .env; fi
	$(VENV)/bin/keynetra migrate --confirm-destructive
	$(VENV)/bin/keynetra config doctor
	$(VENV)/bin/python -m pytest -q tests/test_api_contract.py tests/test_compiled_policies.py

smoke:
	$(PYTHON) -m pytest -q tests/test_api_contract.py tests/test_compiled_policies.py tests/test_doctor.py
