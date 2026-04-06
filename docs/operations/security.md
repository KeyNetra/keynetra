---
title: Security
---

# Security

Security behavior is implemented across config, middleware, and route dependencies.

This page documents the security mechanisms currently implemented in the repository.

## Authentication Methods

- API key header (`X-API-Key`)
- JWT bearer token
- Optional OIDC/JWKS token verification
- Admin login endpoint (`/admin/login`) issuing JWT

Key implementation files:

- `keynetra/config/security.py`
- `keynetra/config/admin_auth.py`
- `keynetra/api/routes/admin_auth.py`

## Authorization for Management APIs

Management endpoints enforce tenant role levels:

- viewer
- developer
- admin

Role checks are wired through `require_management_role(...)`.

API keys are treated as admin-level principals for management paths by default behavior in current implementation.

## Rate Limiting and Idempotency

- Rate limiting middleware: `keynetra/config/rate_limit.py`
- Idempotency middleware: `keynetra/api/middleware/idempotency.py`
- Idempotency storage: `keynetra/domain/models/idempotency.py`

## API Version and Request Tracking

- Version negotiation: `X-API-Version` middleware
- Request IDs and structured request completion logs

## Recommended Operational Baselines

- rotate API keys and JWT secrets regularly
- use hashed API key mode (`KEYNETRA_API_KEY_HASHES`) in production
- avoid default admin credentials outside local development
- run behind TLS-terminating proxy or gateway

## Disclosure Policy

See repository policy:

- `SECURITY.md`

## Related Pages

- [API Reference](../reference/api-reference.md)
- [Environment Variables](../reference/environment-variables.md)
- [Troubleshooting](troubleshooting.md)
