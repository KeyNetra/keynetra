---
title: Consistency and Revisions
---

# Consistency and Revisions

KeyNetra uses tenant revisions and cache namespace strategies to keep authorization decisions coherent during policy and relationship changes.

## Consistency Modes

Access requests can use different consistency behavior, including eventual cached reads and stricter consistency paths.

Primary implementation:

- `keynetra/services/authorization.py`

## Revision Tracking

Tenant revisions and policy versions are used to isolate stale decisions.

Primary implementation:

- `keynetra/services/revisions.py`
- `keynetra/domain/models/tenant.py`

## Cache Namespace Bumping

When policies, ACL entries, or relationships change, relevant cache namespaces are bumped and stale decision keys become invalid.

Related caches:

- policy cache
- relationship cache
- ACL cache
- access index cache
- decision cache

## Distributed Invalidation

In multi-instance deployments, policy invalidations are distributed through Redis Pub/Sub.

Related implementation:

- `keynetra/infrastructure/cache/policy_distribution.py`
- `keynetra/api/main.py` (`_start_policy_subscriber`)

## Related Pages

- [Caching and Consistency](../architecture/caching-and-consistency.md)
- [Observability](../operations/observability.md)
- [Troubleshooting](../operations/troubleshooting.md)

