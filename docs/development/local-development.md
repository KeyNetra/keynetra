---
title: Local Development
---

# Local Development

This page describes the recommended development workflow for contributors and maintainers.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

Optional: run local services via Docker while running the app locally.

## Core Commands

From `Makefile`:

- `make install`
- `make test`
- `make lint`
- `make format`
- `make migrate`
- `make run`

## Run API

```bash
make run
```

or

```bash
uvicorn keynetra.api.main:app --reload
```

Or use CLI:

```bash
python -m keynetra.cli serve --config ./keynetra.yaml
```

## Seed Sample Data

```bash
python -m keynetra.cli seed-data --reset
```

## Developer-Facing Endpoints

In development/local environment (`KEYNETRA_ENVIRONMENT=development`), sample endpoints are available:

- `GET /dev/sample-data`
- `POST /dev/sample-data/seed`

## Related Pages

- [Testing Strategy](testing.md)
- [Migrations](migrations.md)
- [Contributing](contributing.md)
