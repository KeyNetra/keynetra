---
title: End-to-End API Flow
---

# End-to-End API Flow

This walkthrough covers a practical management-to-decision flow using HTTP APIs.

For file-based bootstrapping, use [Example Files](example-files.md) in `docs/examples/assets/`.

## Goal

- Create a policy
- Validate access decision
- Simulate a policy change
- Review audit records

## 1. Start KeyNetra

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve
```

## 2. Create Policy

```bash
curl -s -X POST http://localhost:8000/policies \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "action": "read",
    "effect": "allow",
    "priority": 50,
    "conditions": {
      "policy_key": "allow-read-admin",
      "role": "admin"
    }
  }' | jq .
```

## 3. Evaluate Access

```bash
curl -s -X POST http://localhost:8000/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "action": "read",
    "resource": {"resource_type": "document", "resource_id": "doc-1"},
    "context": {}
  }' | jq .
```

You should see `data.allowed=true` when policy and payload conditions match.

## 4. Simulate Deny Override

```bash
curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "simulate": {
      "policy_change": "deny:\n  action: read\n  priority: 100\n  policy_key: deny-read-admin-temp\n  when:\n    role: admin"
    },
    "request": {
      "user": {"id": "u1", "role": "admin"},
      "action": "read",
      "resource": {"resource_type": "document", "resource_id": "doc-1"},
      "context": {}
    }
  }' | jq .
```

Use this output to confirm behavior before persisting policy updates.

## 5. Read Audit Trail

```bash
curl -s "http://localhost:8000/audit?user_id=u1&resource_id=doc-1&limit=10" \
  -H "X-API-Key: devkey" | jq .
```

## 6. Cleanup Policy

```bash
curl -s -X DELETE http://localhost:8000/policies/allow-read-admin \
  -H "X-API-Key: devkey" | jq .
```

## Related Pages

- [API Reference](../reference/api-reference.md)
- [Policy File Formats](../reference/policy-files.md)
- [Policy Patterns](policy-patterns.md)
