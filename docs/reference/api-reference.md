---
title: API Reference
---

# API Reference

This page documents the implemented HTTP API surface in this repository.

Implementation entrypoints:

- `keynetra/api/main.py`
- `keynetra/api/service_modes.py`
- `keynetra/api/routes/*`

OpenAPI contract:

- `contracts/openapi/keynetra-v0.1.0.yaml`

## Base URL

Local default:

```text
http://localhost:8000
```

## Authentication

Supported request auth:

- `X-API-Key: <key>`
- `Authorization: Bearer <jwt>`
- Admin login via `POST /admin/login`

Many management endpoints require elevated roles enforced in route dependencies.

## Service Modes and Endpoint Availability

Configured via `KEYNETRA_SERVICE_MODE`:

- `all`: exposes access and management APIs
- `access-api`: exposes health/metrics + access endpoints
- `policy-store`: exposes health/metrics + management endpoints
- `policy-engine`: exposes health/metrics + access endpoints

If an endpoint is missing in runtime, verify the service mode first.

## Response Envelope

Most endpoints return the standard envelope defined in `keynetra/domain/schemas/api.py`.

Typical success shape:

```json
{
  "success": true,
  "data": {},
  "request_id": "..."
}
```

## Endpoint Groups

### Health and Observability

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /metrics`

Example:

```bash
curl -s http://localhost:8000/health/ready | jq .
```

### Access Decision

- `POST /check-access`
- `POST /check-access-batch`
- `POST /simulate`

Single decision example:

```bash
curl -s -X POST http://localhost:8000/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "action": "read",
    "resource": {"resource_type": "document", "resource_id": "doc-1"},
    "context": {}
  }' | jq .
```

Batch decision example:

```bash
curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "items": [
      {"action": "read", "resource": {"resource_type": "document", "resource_id": "doc-1"}, "context": {}},
      {"action": "write", "resource": {"resource_type": "document", "resource_id": "doc-1"}, "context": {}}
    ]
  }' | jq .
```

### Policy Simulation and Impact

- `POST /simulate-policy`
- `POST /impact-analysis`

Example:

```bash
curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "simulate": {
      "policy_change": "allow:\n  action: read\n  priority: 10\n  policy_key: read-admin\n  when:\n    role: admin"
    },
    "request": {
      "user": {"id": "u1", "role": "admin"},
      "action": "read",
      "resource": {"resource_type": "document", "resource_id": "doc-1"},
      "context": {}
    }
  }' | jq .
```

### Policy Management

- `GET /policies`
- `POST /policies`
- `PUT /policies/{policy_key}`
- `DELETE /policies/{policy_key}`
- `POST /policies/dsl`
- `POST /policies/{policy_key}/rollback/{version}`

Create policy example:

```bash
curl -s -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "action": "read",
    "effect": "allow",
    "priority": 20,
    "conditions": {"policy_key": "document-read-admin", "role": "admin"}
  }' | jq .
```

### RBAC, ACL, Relationships, and Models

RBAC endpoints:

- `GET /roles`
- `POST /roles`
- `PUT /roles/{role_id}`
- `DELETE /roles/{role_id}`
- `GET /roles/{role_id}/permissions`
- `POST /roles/{role_id}/permissions`
- `DELETE /roles/{role_id}/permissions/{permission_id}`
- `GET /permissions`
- `POST /permissions`
- `PUT /permissions/{permission_id}`
- `DELETE /permissions/{permission_id}`
- `GET /permissions/{permission_id}/roles`

ACL endpoints:

- `POST /acl`
- `GET /acl/{resource_type}/{resource_id}`
- `DELETE /acl/{acl_id}`

Relationship endpoints:

- `GET /relationships`
- `POST /relationships`

Authorization model endpoints:

- `POST /auth-model`
- `GET /auth-model`

### Audit, Playground, and Dev Utilities

- `GET /audit`
- `POST /playground/evaluate`
- `GET /dev/sample-data`
- `POST /dev/sample-data/seed`

## Common Error Cases

- `401`: missing or invalid API key/JWT
- `403`: authenticated but insufficient management role
- `422`: payload validation error
- `500`: database or internal processing failure

Inspect `request_id` in error responses to trace logs.

## Versioning and Middleware

Versioning middleware:

- `keynetra/api/middleware/versioning.py`

Other key middleware:

- request id: `keynetra/api/middleware/request_id.py`
- rate limit: `keynetra/config/rate_limit.py`
- idempotency: `keynetra/api/middleware/idempotency.py`
- structured error envelope: `keynetra/api/middleware/errors.py`

## Related Pages

- [CLI Reference](cli-reference.md)
- [Configuration Files](configuration-files.md)
- [End-to-End API Example](../examples/end-to-end-api-flow.md)
- [Security](../operations/security.md)
