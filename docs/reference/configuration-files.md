---
title: Configuration Files
---

# Configuration Files

KeyNetra supports YAML, JSON, and TOML configuration files.

Loader implementation:

- `keynetra/config/config_loader.py`

## Precedence

When multiple configuration sources are used, effective settings follow this order:

1. CLI flags (`--host`, `--port`, command-specific options)
2. Environment variables (`KEYNETRA_*`)
3. Config file values loaded via `--config`
4. Built-in defaults in `keynetra/config/settings.py`

## Supported Keys

Top-level keys currently mapped by loader:

- `database.url`
- `redis.url`
- `policies.path` and `policies.paths`
- `models.path` and `models.paths`
- `policy_paths`
- `model_paths`
- `seed_data`
- `server.host`
- `server.port`

These are transformed into `KEYNETRA_*` environment variables.

## Field Mapping

| Config Field | Type | Purpose | Mapped Environment Variable |
| --- | --- | --- | --- |
| `database.url` | string | SQLAlchemy database URL | `KEYNETRA_DATABASE_URL` |
| `redis.url` | string | Redis connection URL | `KEYNETRA_REDIS_URL` |
| `policies.path` / `policies.paths` | string/list | Policy file or directory inputs | `KEYNETRA_POLICY_PATHS` |
| `policy_paths` | list | Alternate explicit policy list | `KEYNETRA_POLICY_PATHS` |
| `models.path` / `models.paths` | string/list | Auth model files | `KEYNETRA_MODEL_PATHS` |
| `model_paths` | list | Alternate explicit model list | `KEYNETRA_MODEL_PATHS` |
| `seed_data` | bool | Auto-seed sample data in local mode | `KEYNETRA_AUTO_SEED_SAMPLE_DATA` |
| `server.host` | string | API bind host | `KEYNETRA_SERVER_HOST` |
| `server.port` | int | API bind port | `KEYNETRA_SERVER_PORT` |

## Example YAML

```yaml
database:
  url: postgresql+psycopg://keynetra:keynetra@localhost:5432/keynetra

redis:
  url: redis://localhost:6379/0

policies:
  paths:
    - ./docs/examples/assets/policies

models:
  path: ./docs/examples/assets/auth-model.yaml

seed_data: false

server:
  host: 0.0.0.0
  port: 8000
```

## Example JSON

```json
{
  "database": { "url": "sqlite+pysqlite:///./keynetra.db" },
  "redis": { "url": "redis://localhost:6379/0" },
  "policy_paths": ["./docs/examples/assets/policies"],
  "model_paths": ["./docs/examples/assets/auth-model.yaml"],
  "seed_data": true,
  "server": { "host": "0.0.0.0", "port": 8000 }
}
```

## Example TOML

```toml
[database]
url = "sqlite+pysqlite:///./keynetra.db"

[redis]
url = "redis://localhost:6379/0"

[policies]
path = "./docs/examples/assets/policies"

[models]
path = "./docs/examples/assets/auth-model.yaml"

seed_data = true

[server]
host = "0.0.0.0"
port = 8000
```

## Runtime Usage

API server:

```bash
python -m keynetra.cli serve --config ./docs/examples/assets/keynetra.yaml
```

Decision check using the same config:

```bash
python -m keynetra.cli check \
  --config ./docs/examples/assets/keynetra.yaml \
  --api-key devkey \
  --user '{"id":"u1","role":"admin"}' \
  --action read \
  --resource '{"resource_type":"document","resource_id":"doc-1"}'
```

## Validation Tips

- Use absolute paths in containerized environments.
- Keep policy/model paths under version control for repeatable deployments.
- Run `compile-policies` after any policy path change.
- Run `doctor --service core` before production rollout.

## Related Pages

- [Environment Variables](environment-variables.md)
- [Policy File Formats](policy-files.md)
- [Authorization Model Files](auth-model-files.md)
- [CLI Reference](cli-reference.md)
