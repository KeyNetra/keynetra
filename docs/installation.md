# Installation

## Supported Runtime

- Python `3.11+`
- SQLite for local development
- PostgreSQL recommended for production
- Redis optional for distributed cache coordination

## Install From Source

```bash
git clone https://github.com/keynetra/keynetra.git
cd keynetra
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
```

## Install As A Package

```bash
pip install keynetra
```

This installs:

- the `keynetra` CLI
- the embedded Python SDK facade
- the FastAPI application package

## Verify Installation

```bash
keynetra version
keynetra --help
python -c "import keynetra; print(keynetra.__version__)"
```

## Developer Tooling

```bash
ruff check .
black --check .
isort --check-only .
mypy keynetra
pytest --cov=keynetra --cov-report=term-missing
```

## Optional Components

- Redis: set `KEYNETRA_REDIS_URL`
- OpenTelemetry FastAPI instrumentation: installed with the main dependency set and enabled with `KEYNETRA_OTEL_ENABLED=true`
- Docker: see [deployment/docker.md](deployment/docker.md)
- Helm: see [deployment/helm.md](deployment/helm.md)
