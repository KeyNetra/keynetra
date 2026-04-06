---
title: System Architecture
---

# System Architecture

KeyNetra follows a layered architecture with strict boundary control.

## Layers

Key principle: the engine layer remains pure and deterministic, while side effects stay in service/infrastructure layers.

## Engine Layer

- Location: `keynetra/engine/`
- Contains deterministic authorization logic.
- No DB, cache, HTTP, or external state access.

Primary engine implementation:

- `keynetra/engine/keynetra_engine.py`
- `keynetra/engine/compiled/`
- `keynetra/engine/model_graph/`

## Service Layer

- Location: `keynetra/services/`
- Orchestrates repositories, cache, revision consistency, and resilience.

Main orchestrator:

- `keynetra/services/authorization.py`

## Infrastructure Layer

- Location: `keynetra/infrastructure/`
- Owns cache backends, repositories, DB session handling, and transport adapters.

Examples:

- `keynetra/infrastructure/cache/`
- `keynetra/infrastructure/repositories/`
- `keynetra/infrastructure/storage/session.py`

## API Layer

- Location: `keynetra/api/`
- FastAPI routes and middleware only.
- Delegates decision logic to services.

Entry point:

- `keynetra/api/main.py`

## Configuration Layer

- Location: `keynetra/config/`
- Environment settings, security, tenancy, and file-based config loading.

## Domain Layer

- Location: `keynetra/domain/`
- SQLAlchemy data models and API schema contracts.

## Request Lifecycle

1. API receives request and authenticates principal.
2. Service hydrates tenant context and evaluation input.
3. Engine evaluates with deterministic decision order.
4. Service handles cache/audit/revision side effects.
5. API returns normalized response envelope.

## Architecture Guardrails

- `keynetra/` code does not depend on `infra/`.
- Route handlers avoid business logic and delegate to services.
- Engine evaluations use explicit inputs only, with no hidden lookups.

## Related Pages

- [Authorization Pipeline](authorization-pipeline.md)
- [Caching and Consistency](caching-and-consistency.md)
- [API Reference](../reference/api-reference.md)
- [Data Models and Storage](data-models.md)
