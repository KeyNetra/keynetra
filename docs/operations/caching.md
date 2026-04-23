# Caching

KeyNetra uses layered caching to keep authorization latency low without hiding policy changes.

## Cache Layers

1. Local in-process TTL decision cache
2. Optional Redis-backed distributed decision cache
3. Policy cache
4. Relationship cache
5. ACL and access-index caches

## Authorization Decision Caching

The authorization service stores short-lived cached decisions keyed by:

- tenant
- policy version
- revision
- user payload
- action
- resource payload
- context payload

The distributed cache key is derived from a stable hash of the explicit hydrated input.

## Local TTL Cache

The release-hardened runtime includes a bounded in-process cache for hot authorization decisions.

- thread-safe
- bounded memory
- short TTL
- warms before the Redis-backed decision cache

This keeps repeated checks fast even when Redis is unavailable.

## Optional Redis Cache

Enable Redis with:

```bash
export KEYNETRA_REDIS_URL=redis://localhost:6379/0
```

With Redis enabled, KeyNetra can share decision cache entries and invalidation across instances.

## Invalidation

- policy updates bump tenant decision namespaces
- relationship updates invalidate relationship/access-index state and bump decision namespaces
- ACL updates invalidate resource-specific caches

## Practical Guidance

- keep `KEYNETRA_DECISION_CACHE_TTL_SECONDS` short
- use Redis in multi-replica environments
- rely on explain traces and revision ids when debugging cache behavior
