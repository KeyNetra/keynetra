---
title: Request Evaluation Lifecycle
---

# Request Evaluation Lifecycle

This page explains what happens from request intake to final authorization decision.

## 1) Request Intake

An access request includes:

- `user`
- `action`
- `resource`
- optional `context`

Transport entry points:

- `POST /check-access`
- `POST /check-access-batch`

## 2) Service Hydration

The authorization service resolves tenant state, policies, relationships, ACL data, and cached decision candidates.

Key implementation:

- `keynetra/services/authorization.py`

## 3) Engine Evaluation

The engine performs deterministic evaluation across direct permissions, ACL, RBAC, relationships, schema permissions, policy graph, and default deny.

Key implementation:

- `keynetra/engine/keynetra_engine.py`

## 4) Decision Output

The system returns:

- decision (`allow` or `deny`)
- reason and optional policy ID
- explain trace entries for audit/debugging

## 5) Side Effects

After decision calculation, the service may:

- write audit records
- update decision cache
- apply revision/consistency behavior

## Related Pages

- [Authorization Pipeline](../architecture/authorization-pipeline.md)
- [Caching and Consistency](../architecture/caching-and-consistency.md)
- [API Reference](../reference/api-reference.md)

