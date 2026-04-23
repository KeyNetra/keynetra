# Architecture

KeyNetra enforces clean layering so policy decisions remain deterministic and easy to audit.

## Layers

- `keynetra.api`: HTTP transport, request/response models, middleware
- `keynetra.services`: orchestration, validation, hydration, cache coordination
- `keynetra.engine`: pure authorization engine
- `keynetra.infrastructure`: storage, repository, cache, logging, metrics adapters
- `keynetra.domain`: shared models and schemas
- `keynetra.config`: settings, file loading, security guardrails

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI Route
    participant Service as AuthorizationService
    participant Cache as Local/Redis Cache
    participant DB as Repositories
    participant Engine as KeyNetraEngine

    Client->>API: POST /check-access
    API->>Service: authorize(...)
    Service->>Cache: decision lookup
    alt cache miss
        Service->>DB: tenant, user, relationships, policies
        Service->>Engine: decide(AuthorizationInput)
        Engine-->>Service: AuthorizationDecision
        Service->>Cache: store short-TTL decision
    end
    Service-->>API: AuthorizationResult
    API-->>Client: JSON response
```

## Evaluation Order

The engine evaluates authorization in a deterministic sequence:

1. Direct user permissions
2. ACL entries
3. Role-based permissions
4. Relationship access index
5. Authorization model / compiled policy graph
6. Default deny

## Why This Matters

- Deterministic order makes explanations stable.
- The engine is side-effect free.
- Caches are outside the engine, so a decision can always be recomputed from explicit input.

## Further Reading

- [Authorization Models](authorization-models.md)
- [Policy Engine](policy-engine.md)
- [Caching](operations/caching.md)
