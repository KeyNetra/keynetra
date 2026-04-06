# Integration Cookbook (Practical)

This page gives end-to-end integration patterns with copy-paste examples.

## 1) Backend middleware pattern

Use KeyNetra before protected handlers.

Pseudo-flow:

1. Build request payload from authenticated user + route context
2. Call `/check-access`
3. Deny with 403 when `allowed=false`
4. Log `reason` + `policy_id` for debugging

Example payload:

```json
{
  "user": {"id": "u-42", "role": "manager", "permissions": ["approve_payment"]},
  "action": "approve_payment",
  "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000},
  "context": {"department": "finance", "request_id": "req-123"}
}
```

## 2) Frontend permission matrix pattern

When UI needs many permissions (buttons, tabs, actions), call one batch endpoint.

Example:

```bash
curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u-42", "role": "manager", "permissions": ["approve_payment"]},
    "items": [
      {"action": "approve_payment", "resource": {"resource_type": "payment", "resource_id": "pay-1", "amount": 500}},
      {"action": "approve_payment", "resource": {"resource_type": "payment", "resource_id": "pay-2", "amount": 500000}},
      {"action": "read", "resource": {"resource_type": "document", "resource_id": "doc-1"}}
    ]
  }' | jq .
```

## 3) Safe policy rollout pattern

For policy PRs or release pipelines:

1. Run `/simulate-policy` with representative cases
2. Run `/impact-analysis`
3. Require explicit approval for high-impact changes

### Step A: simulate one critical flow

```bash
curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "simulate": {
      "policy_change": "deny:\n  action: approve_payment\n  priority: 1\n  policy_key: emergency-freeze\n  when:\n    department: finance"
    },
    "request": {
      "user": {"id": "u-42", "role": "manager", "department": "finance"},
      "action": "approve_payment",
      "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 1000},
      "context": {}
    }
  }' | jq .
```

### Step B: analyze blast radius

```bash
curl -s -X POST http://localhost:8000/impact-analysis \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "policy_change": "deny:\n  action: approve_payment\n  priority: 1\n  policy_key: emergency-freeze\n  when:\n    department: finance"
  }' | jq .
```

## 4) Incident-debug pattern

If an expected allow becomes deny in production:

1. Replay request through `/simulate`
2. Inspect `failed_conditions`
3. Inspect `explain_trace`
4. Confirm latest `revision`

Example:

```bash
curl -s -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "u-42", "role": "manager"},
    "action": "approve_payment",
    "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 250000},
    "context": {"department": "finance"}
  }' | jq .
```

## 5) Language-agnostic response contract

Always parse these fields from responses:

- `data.allowed` or `data.decision`
- `data.reason`
- `data.policy_id`
- `data.revision`
- `meta.request_id`

These fields are enough for product behavior, logging, and support triage.
