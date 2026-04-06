# Configuration Guide

KeyNetra supports two practical configuration styles:

1. Environment variables (fastest)
2. YAML/JSON/TOML config file passed to CLI with `--config`

## Environment variable setup

```bash
export KEYNETRA_API_KEYS=devkey
export KEYNETRA_DATABASE_URL=sqlite+pysqlite:///./keynetra.db
export KEYNETRA_REDIS_URL=
export KEYNETRA_POLICY_PATHS=./policies
export KEYNETRA_MODEL_PATHS=./models
python -m keynetra.cli serve
```

## YAML config file

Example `keynetra.yaml`:

```yaml
database:
  url: sqlite+pysqlite:///./keynetra.db
redis:
  url: null
policies:
  path: ./policies
models:
  path: ./models
server:
  host: 0.0.0.0
  port: 8000
seed_data: false
```

Run with config file:

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve --config ./keynetra.yaml
```

Note:

- API keys are still configured via environment (`KEYNETRA_API_KEYS`).

## JSON config file

```json
{
  "database": {"url": "sqlite+pysqlite:///./keynetra.db"},
  "redis": {"url": null},
  "policy_paths": ["./policies"],
  "model_paths": ["./models"],
  "server": {"host": "0.0.0.0", "port": 8000},
  "seed_data": false
}
```

Run:

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve --config ./keynetra.json
```

## Most useful env vars

- `KEYNETRA_API_KEYS`
- `KEYNETRA_DATABASE_URL`
- `KEYNETRA_REDIS_URL`
- `KEYNETRA_POLICY_PATHS`
- `KEYNETRA_MODEL_PATHS`
- `KEYNETRA_RATE_LIMIT_PER_MINUTE`
- `KEYNETRA_RATE_LIMIT_BURST`
- `KEYNETRA_SERVER_HOST`
- `KEYNETRA_SERVER_PORT`
