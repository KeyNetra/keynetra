---
title: Authorization Pipeline
---

# Authorization Pipeline

`KeyNetraEngine` evaluates authorization in deterministic order.

Source of truth:

- `keynetra/engine/keynetra_engine.py`

## Evaluation Order

1. Direct user permissions
2. ACL checks
3. RBAC role permissions
4. Relationship index checks
5. Schema permission graph checks
6. Compiled policy graph evaluation
7. Default deny

This order is fixed by engine implementation and is important when multiple models can match the same request.

## Input Contract

Engine accepts an explicit `AuthorizationInput` object:

- `user`
- `action`
- `resource`
- `context`
- hydrated ACL/relationship/index/model graph fields from service layer

No hidden data fetch occurs inside the engine.

The service layer pre-hydrates policy data, relationships, ACL data, and optional compiled model graphs before the engine runs.

## Decision Output

`AuthorizationDecision` includes:

- `allowed`
- `decision` (`allow` or `deny`)
- `reason`
- `policy_id`
- `matched_policies`
- `failed_conditions`
- `explain_trace`

`explain_trace` is designed for debugging and auditability of decision paths.

## Service Responsibilities

Service constructs full input and handles:

- policy retrieval and compilation lookup
- relationship and ACL hydration
- decision caching
- revision-aware consistency
- audit writes

Primary file:

- `keynetra/services/authorization.py`

## Example Decision Call

```python
from keynetra.engine import KeyNetraEngine

engine = KeyNetraEngine([
    {"action": "read", "effect": "allow", "priority": 10, "conditions": {"role": "admin"}}
])

decision = engine.check_access(
    subject="user:123",
    action="read",
    resource="document:abc",
    context={"role": "admin"},
)
```

## Related Pages

- [Data Models and Storage](data-models.md)
- [Caching and Consistency](caching-and-consistency.md)
- [Policy File Formats](../reference/policy-files.md)
- [Authorization Model Files](../reference/auth-model-files.md)
