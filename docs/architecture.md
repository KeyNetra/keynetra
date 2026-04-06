# Architecture Guide

This page explains how an authorization request flows through KeyNetra.

## Core components

- API layer: FastAPI routes in `keynetra/api/routes/`
- Service layer: orchestration in `keynetra/services/`
- Engine layer: policy evaluation in `keynetra/engine/`
- Data layer: repositories in `keynetra/infrastructure/repositories/`
- Cache layer: in-memory/Redis caches in `keynetra/infrastructure/cache/`
- Observability: metrics/logging/audit support

## Request flow

```text
Client request
  -> API auth (API key or JWT)
  -> Request validation
  -> AuthorizationService.authorize(...)
  -> Load policies / relationships / ACL / model graph
  -> Evaluate decision (RBAC/ABAC/ACL/ReBAC)
  -> Build explain_trace + reason + policy_id
  -> Write audit / update metrics
  -> Return response envelope
```

## Policy evaluation flow (simplified)

1. Read request (`user`, `action`, `resource`, `context`)
2. Evaluate explicit allows/denies (policies and ACL where applicable)
3. Evaluate relationship-based grants (ReBAC model graph)
4. Apply priority and first-match logic
5. Return `allow` or `deny`
6. If no policy matches, deny by default

## Consistency and revision tokens

Responses include `revision` values.
Use revision tokens when you need stronger consistency between write and read operations.

## Caching behavior

KeyNetra uses cache adapters to reduce repeated policy and relationship lookups.
When policies or relationships change, namespaces/entries are invalidated.

## Where to read next

- [API Endpoints](api-endpoints.md)
- [Policy Guide](policies.md)
- [Best Practices](best-practices.md)
