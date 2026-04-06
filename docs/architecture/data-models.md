---
title: Data Models and Storage
---

# Data Models and Storage

KeyNetra persists state in relational tables with Alembic migration control.

This page maps high-level authorization concepts to concrete database tables.

## Core Tables

Defined in `keynetra/domain/models/`:

- `tenant.py`: `tenants`
- `rbac.py`: `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- `relationship.py`: `relationships`
- `acl.py`: `resource_acl`
- `policy_versioning.py`: `policies`, `policy_versions`
- `auth_model.py`: `auth_models`
- `audit.py`: `audit_logs`
- `idempotency.py`: `idempotency_records`

## Concept to Table Mapping

- Tenancy and revisions: `tenants`
- RBAC: `users`, `roles`, `permissions`, `user_roles`, `role_permissions`
- ReBAC edges: `relationships`
- ACL rules: `resource_acl`
- Policy history: `policies`, `policy_versions`
- Schema modeling: `auth_models`
- Decision audit: `audit_logs`
- Idempotent write replay: `idempotency_records`

## Migration System

- Alembic config: `alembic.ini`
- Runtime env: `alembic/env.py`
- Revisions: `alembic/versions/*.py`

Current revision history includes baseline plus tenant policy versioning, relationships, ACL, auth model, audit explainability, and idempotency support.

See [Migrations](../development/migrations.md) for execution details.

## Repository Pattern

Storage access is routed through repository implementations in:

- `keynetra/infrastructure/repositories/`

Services use protocol interfaces from:

- `keynetra/services/interfaces.py`

## Related Pages

- [Migrations](../development/migrations.md)
- [API Reference](../reference/api-reference.md)
- [Authorization Pipeline](authorization-pipeline.md)
