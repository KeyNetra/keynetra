# API Reference

KeyNetra exposes a FastAPI-based REST API for authorization and administration.

## Core Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/check-access` | Evaluate one authorization request |
| `POST` | `/check-access-batch` | Evaluate multiple actions for one user |
| `POST` | `/simulate` | Run a simulated authorization request |
| `GET` | `/health` | Basic liveness check |
| `GET` | `/health/ready` | Readiness check |
| `GET` | `/metrics` | Prometheus metrics |

Administrative and management routes are also available for ACL, roles, policies, audit, and auth-model operations.

## Authentication

Supported headers:

- `X-API-Key: <key>`
- `Authorization: Bearer <jwt>`

Optional tenant routing:

- `X-Tenant-Id: <tenant>`

## Example Request

```bash
curl -s -X POST http://127.0.0.1:8080/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "action": "read",
    "resource": {"resource_type": "document", "resource_id": "doc-1"},
    "context": {}
  }'
```

## OpenAPI

Generate a fresh contract:

```bash
keynetra generate-openapi --output docs/openapi.json
```

Validate a contract:

```bash
keynetra check-openapi --contract docs/openapi.json
```

The generated contract is versioned at:

- `contracts/openapi.json`
- `contracts/openapi.yaml`
- `docs/openapi.json`

## Error Shape

Errors use the project response envelope and avoid raw stack traces:

```json
{
  "data": null,
  "meta": {
    "request_id": "..."
  },
  "error": {
    "code": "validation_error",
    "message": "tenant is required"
  }
}
```
