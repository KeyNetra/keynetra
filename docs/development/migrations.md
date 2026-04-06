---
title: Migrations
---

# Migrations

KeyNetra uses Alembic for schema migrations.

All schema changes should be tracked with migration files under `alembic/versions/`.

## Files

- `alembic.ini`
- `alembic/env.py`
- `alembic/versions/*.py`
- `keynetra/migrations.py` (destructive migration detection utility)

## Run Migrations

```bash
python -m keynetra.cli migrate
```

If destructive revisions exist and are intentional:

```bash
python -m keynetra.cli migrate --confirm-destructive
```

## Migration Safety

`keynetra/migrations.py` detects unapplied destructive operations (drop table/column) and blocks execution unless explicitly confirmed.

## Migration Coverage

Revision files currently include schema for:

- RBAC tables
- tenant and policy versioning
- relationships
- audit explainability fields
- idempotency records
- ACL entries
- authorization model revisions

## Docker Migrations

Container startup script runs migrations when:

- `KEYNETRA_RUN_MIGRATIONS=1`

Reference:

- `infra/docker/start.sh`

## Related Pages

- [Data Models and Storage](../architecture/data-models.md)
- [Troubleshooting](../operations/troubleshooting.md)
- [CI/CD and Release](ci-cd-release.md)
