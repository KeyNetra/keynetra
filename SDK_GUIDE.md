# SDK Guide

KeyNetra can be embedded directly into Python services when you want in-process authorization checks without running the FastAPI control plane.

## Install

```bash
pip install keynetra
```

## Minimal Usage

```python
from keynetra import KeyNetra

engine = KeyNetra.from_config(
    {
        "database_url": "sqlite+pysqlite:///./keynetra.db",
        "policies_json": """
        [
          {
            "action": "read",
            "effect": "allow",
            "priority": 10,
            "conditions": {"role": "admin"}
          }
        ]
        """,
    }
)

result = engine.check_access(
    user={"id": "u1", "role": "admin"},
    action="read",
    resource={"id": "doc-1", "resource_type": "document"},
    context={},
)

assert result["allowed"] is True
```

## Configuration Sources

`KeyNetra.from_config(...)` accepts the same effective settings used by the API server.

- `database_url`: SQLAlchemy connection string.
- `policies_json`: inline policy definitions.
- `policy_paths`: comma-separated file paths for YAML/JSON policy files.
- `model_paths`: comma-separated authorization model file paths.
- `strict_tenancy`: require tenant resolution explicitly.
- `service_timeout_seconds`: repository and cache timeout budget.

Environment-backed usage is also supported:

```python
from keynetra import KeyNetra

engine = KeyNetra.from_env()
```

## Check Access

```python
decision = engine.check_access(
    user={"id": "u2", "role": "viewer"},
    action="write",
    resource={"id": "doc-9", "resource_type": "document"},
    context={"tenant": "acme"},
)

print(decision["decision"])
print(decision["reason"])
```

The returned payload includes:

- `allowed`
- `decision`
- `reason`
- `policy_id`
- `matched_policies`
- `explain_trace`
- `revision`

## Recommended Patterns

- Reuse a single `KeyNetra` instance per process.
- Prefer explicit `resource_type` and `resource_id` fields for ACL and ReBAC lookups.
- Load policies from versioned files in production, not inline strings.
- Treat `revision` as an audit/debug value, not a cache key outside KeyNetra.

## Error Handling

- Invalid configuration raises a standard Python exception during engine creation.
- Missing tenants or malformed authorization input surface as runtime errors from `check_access(...)`.
- In production, pair embedded usage with explicit health checks around policy/model loading.

## When To Use The API Server Instead

Use `keynetra serve` instead of embedded mode when you need:

- centralized multi-tenant management APIs
- OpenAPI contracts
- HTTP-based policy simulation and impact analysis
- shared control-plane metrics and rate limiting
