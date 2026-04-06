---
title: Authorization Models
---

# Authorization Models

KeyNetra supports multiple authorization models that can be composed in a single decision flow.

## RBAC

Role-Based Access Control is implemented through users, roles, permissions, and role-permission bindings.

Related implementation:

- `keynetra/domain/models/rbac.py`
- `keynetra/api/routes/roles.py`
- `keynetra/api/routes/permissions.py`

## ACL

Access Control Lists provide resource-scoped, subject-specific allow/deny entries.

Related implementation:

- `keynetra/domain/models/acl.py`
- `keynetra/api/routes/acl.py`

## ReBAC

Relationship-Based Access Control uses relationship edges between subjects and objects.

Related implementation:

- `keynetra/domain/models/relationship.py`
- `keynetra/api/routes/relationships.py`

## Policy Graph Evaluation

Policy rules are compiled and evaluated as part of the deterministic engine pipeline.

Related implementation:

- `keynetra/engine/compiled/decision_graph.py`
- `keynetra/services/policies.py`

## Schema-Based Authorization Modeling

Authorization models can be defined as schema files and compiled into permission graphs.

Related implementation:

- `keynetra/modeling/schema_parser.py`
- `keynetra/modeling/model_validator.py`
- `keynetra/modeling/permission_compiler.py`

## Related Pages

- [Authorization Pipeline](../architecture/authorization-pipeline.md)
- [Policy File Formats](../reference/policy-files.md)
- [Authorization Model Files](../reference/auth-model-files.md)

