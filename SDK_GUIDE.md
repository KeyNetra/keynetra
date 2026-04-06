# SDK Guide

KeyNetra SDKs are versioned independently from the core engine.

## Repository Scope

This repository contains the authorization engine, API server, CLI, and deployment assets.

SDK implementations are maintained in separate repositories and released on their own cadence.

## Python SDK

- Package: `keynetra-client`
- Install: `pip install keynetra-client`

Basic usage:

```python
from keynetra_client import KeyNetraClient

client = KeyNetraClient("http://localhost:8080")
decision = client.check_access(
    user={"id": "alice"},
    action="read",
    resource={"type": "document", "id": "doc-1"},
)
print(decision.allowed)
```

## API Contract Compatibility

- Server OpenAPI contract: `contracts/openapi/openapi.json`
- Validate API consistency from this repository:

```bash
keynetra check-openapi
```

## Planned SDKs

- Python
- TypeScript
- Go
- Java
