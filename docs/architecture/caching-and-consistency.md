---
title: Caching and Consistency
---

# Caching and Consistency

KeyNetra uses layered caching with Redis backend and in-memory fallback.

Caching is implemented per concern (policy, decision, ACL, relationship, and access index) to reduce latency while preserving deterministic decisions.

## Cache Layers

- Policy cache: `keynetra/infrastructure/cache/policy_cache.py`
- Relationship cache: `keynetra/infrastructure/cache/relationship_cache.py`
- Decision cache: `keynetra/infrastructure/cache/decision_cache.py`
- ACL cache: `keynetra/infrastructure/cache/acl_cache.py`
- Access index cache: `keynetra/infrastructure/cache/access_index_cache.py`

Backend abstraction:

- `keynetra/infrastructure/cache/backends.py`

If Redis is unavailable, KeyNetra falls back to shared in-memory cache adapters in-process.

## Invalidation Model

- Tenant namespace bump for decision cache invalidation.
- Resource/subject scoped invalidation for ACL and relationship changes.
- Policy updates invalidate policy cache and publish distribution events.

This keeps cache behavior predictable across policy and relationship mutations.

## Policy Distribution

Redis pub/sub channel is used for policy update fan-out:

- Event publisher: `keynetra/infrastructure/cache/policy_distribution.py`
- Subscriber startup: `keynetra/api/main.py` (`_start_policy_subscriber`)
- Channel config: `KEYNETRA_POLICY_EVENTS_CHANNEL`

## Consistency Controls

Access requests support consistency modes and revisions:

- eventual cached reads (default)
- fully consistent bypass behavior where configured in service
- revision-driven keying in decision cache

Implementation references:

- `keynetra/services/authorization.py`
- `keynetra/services/revisions.py`

## Operational Notes

- For horizontally scaled deployments, configure Redis to share cache and policy events.
- For local development, in-memory fallback works without Redis.

## Related Pages

- [Authorization Pipeline](authorization-pipeline.md)
- [Observability](../operations/observability.md)
- [Troubleshooting](../operations/troubleshooting.md)
