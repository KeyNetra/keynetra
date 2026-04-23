# SDK Guide

KeyNetra can run as an embedded Python component in addition to the HTTP API.

## Install

```bash
pip install keynetra
```

## Embedded Usage

```python
from keynetra import KeyNetra

engine = KeyNetra.from_config(
    {
        "database_url": "sqlite+pysqlite:///./keynetra.db",
        "policies_json": """
        [
          {"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}}
        ]
        """,
    }
)

decision = engine.check_access(
    user={"id": "u1", "role": "admin"},
    action="read",
    resource={"resource_type": "document", "resource_id": "doc-1", "id": "doc-1"},
    context={},
)

print(decision["allowed"])
```

## Environment-Based Usage

```python
from keynetra import KeyNetra

engine = KeyNetra.from_env()
```

## When To Prefer The API

Use the API server when you need:

- centralized multi-tenant administration
- OpenAPI contracts
- shared observability and rate limiting
- deployment as a dedicated authorization service

Use the embedded SDK when you need:

- in-process authorization checks
- minimal network hops
- deterministic local policy execution
