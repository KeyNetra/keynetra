---
title: Installation
---

# Installation

This page covers local and Docker-based installation paths for KeyNetra.

## Prerequisites

- Python 3.11
- `pip`
- Optional for production/local parity: Docker + Docker Compose

Implementation references:

- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- `Dockerfile`

## Local Python Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
```

## Verify Installation

```bash
python -m keynetra.cli version
python -m keynetra.cli help-cli
```

Expected behavior:

- `version` prints the current package version (for example, `0.1.0`)
- `help-cli` prints the operational command reference

## Optional Docker Setup

```bash
docker compose up --build
```

Development compose:

```bash
docker compose -f docker-compose.dev.yml up --build
```

## Verify Runtime

After startup, run:

```bash
curl -i http://localhost:8000/health/ready
```

You should receive an HTTP `200` response.

## Next

- [Quickstart](quickstart.md)
- [Configuration Files](../reference/configuration-files.md)
- [Environment Variables](../reference/environment-variables.md)
