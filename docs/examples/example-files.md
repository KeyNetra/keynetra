---
title: Example Files
---

# Example Files

All core examples are embedded directly here so you can copy/paste without browsing file paths.

## Runtime Config Example

```yaml
database:
  url: sqlite+pysqlite:///./keynetra.db
redis:
  url: redis://localhost:6379/0
policies:
  paths:
    - ./docs/examples/assets/policies
models:
  path: ./docs/examples/assets/auth-model.yaml
seed_data: true
server:
  host: 0.0.0.0
  port: 8000
```

## Authorization Model Example

```yaml
model:
  schema_version: 1
  type: document
  relations:
    owner: user
    editor:
      - user
    viewer:
      - user
  permissions:
    read: owner or editor or viewer
    write: owner or editor
    delete: owner
```

## Policy Examples

YAML:

```yaml
policies:
  - action: read
    effect: allow
    priority: 10
    policy_id: document-read-admin
    conditions:
      role: admin
      resource_type: document

  - action: delete
    effect: deny
    priority: 40
    policy_id: document-delete-protected
    conditions:
      resource_type: document
      resource_attr: { classification: legal_hold }
```

JSON:

```json
[
  {
    "action": "approve_payment",
    "effect": "allow",
    "priority": 35,
    "policy_id": "payment-approve-manager",
    "conditions": {
      "role": "manager",
      "department": "finance",
      "max_amount": 10000
    }
  }
]
```

Polar-like:

```text
allow action=deploy priority=20 policy_id=ops-deploy-allow role=ops environment=staging
deny action=deploy priority=90 policy_id=ops-deploy-deny-prod role=contractor environment=production
```

## Policy Test Suite Example

```yaml
policies:
  - action: read
    effect: allow
    priority: 10
    policy_id: document-read-admin
    conditions:
      role: admin
      resource_type: document

tests:
  - name: admin can read normal document
    expect: allow
    input:
      user:
        id: alice
        role: admin
      action: read
      resource:
        resource_type: document
        resource_id: doc-1
      context: {}
```

## Quick Validation Flow

```bash
# server
python -m keynetra.cli serve --config docs/examples/assets/keynetra.yaml

# compile and test
python -m keynetra.cli compile-policies --config docs/examples/assets/keynetra.yaml
python -m keynetra.cli test-policy docs/examples/assets/policy_tests.yaml

# apply model
python -m keynetra.cli model apply docs/examples/assets/auth-model.yaml --api-key devkey
```

## Why Embedded Examples

- Show supported file formats (`yaml`, `json`, `polar`).
- Give copy-paste examples directly inside docs.
- Keep docs and runnable assets aligned.

## Related Pages

- [Project Overview](../getting-started/overview.md)
- [Policy File Formats](../reference/policy-files.md)
- [Authorization Model Files](../reference/auth-model-files.md)
