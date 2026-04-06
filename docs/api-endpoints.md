# API Endpoints (Beginner Guide)

All endpoints below are active in this repository and are the primary integration surface.

Base URL:

- `http://localhost:8000`

Auth header:

- `X-API-Key: <your-key>`

Example setup:

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve
```

---

## POST /check-access

Purpose:

- Evaluate one authorization request and return allow/deny with explanation.

Code path:

- Route: `keynetra/api/routes/access.py::check_access`
- Service call: `AuthorizationService.authorize(...)`
- Engine call: `KeyNetraEngine.decide(...)`

Request body:

```json
{
  "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
  "action": "approve_payment",
  "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000},
  "context": {"department": "finance"},
  "consistency": "eventual",
  "revision": null
}
```

Example request:

```bash
curl -s -X POST http://localhost:8000/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
    "action": "approve_payment",
    "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000},
    "context": {"department": "finance"}
  }' | jq .
```

Example response:

```json
{
  "data": {
    "allowed": true,
    "decision": "allow",
    "matched_policies": ["rbac:permissions"],
    "reason": "explicit permission grant",
    "policy_id": "rbac:permissions",
    "explain_trace": [],
    "revision": 1
  },
  "meta": {"request_id": "...", "limit": null, "next_cursor": null, "extra": {}},
  "error": null
}
```

Common use cases:

- Check access before serving a protected API
- Add audit trail context for allow/deny decisions
- Return explanation details to internal admin tools

---

## POST /check-access-batch

Purpose:

- Evaluate multiple actions/resources for the same user in one call.

Code path:

- Route: `keynetra/api/routes/access.py::check_access_batch`
- Service call: `AuthorizationService.authorize_batch(...)`
- Engine call per item: `KeyNetraEngine.decide(...)`

Request body:

```json
{
  "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
  "items": [
    {"action": "approve_payment", "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000}},
    {"action": "delete", "resource": {"resource_type": "payment", "resource_id": "pay-900"}}
  ],
  "consistency": "eventual",
  "revision": null
}
```

Example request:

```bash
curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
    "items": [
      {"action": "approve_payment", "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 5000}},
      {"action": "delete", "resource": {"resource_type": "payment", "resource_id": "pay-900"}}
    ]
  }' | jq .
```

Example response:

```json
{
  "data": {
    "results": [
      {"action": "approve_payment", "allowed": true, "revision": 1},
      {"action": "delete", "allowed": false, "revision": 1}
    ],
    "revision": 1
  },
  "meta": {"request_id": "...", "limit": null, "next_cursor": null, "extra": {}},
  "error": null
}
```

Common use cases:

- Render UI permissions for many buttons/tabs at once
- Reduce network calls from gateway/backend-for-frontend

---

## POST /simulate

Purpose:

- Run a non-persisted decision with full trace and failed conditions.

Code path:

- Route: `keynetra/api/routes/access.py::simulate`
- Service call: `AuthorizationService.simulate(...)`
- Internally uses `authorize(...)` with standard evaluation pipeline

Request body:

- Same shape as `/check-access`

Example request:

```bash
curl -s -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "manager-1", "role": "manager"},
    "action": "approve_payment",
    "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 120000},
    "context": {"department": "finance"}
  }' | jq .
```

Example response:

```json
{
  "data": {
    "decision": "deny",
    "matched_policies": [],
    "reason": "default deny",
    "policy_id": null,
    "explain_trace": [],
    "failed_conditions": ["max_amount"],
    "revision": 1
  },
  "meta": {"request_id": "...", "limit": null, "next_cursor": null, "extra": {}},
  "error": null
}
```

Common use cases:

- Debug policy behavior without changing state
- Build policy authoring tools with explainability

---

## POST /simulate-policy

Purpose:

- Compare decision before and after a proposed policy change.

Code path:

- Route: `keynetra/api/routes/simulation.py::simulate_policy`
- Simulator: `PolicySimulator.simulate_policy_change(...)`
- DSL parser: `keynetra/services/policy_dsl.py::dsl_to_policy`

Note:

- Requires management role (`viewer` or higher). API key auth works as admin in this repo.

Request body:

```json
{
  "simulate": {
    "policy_change": "allow:\n  action: share_document\n  priority: 1\n  policy_key: share-admin\n  when:\n    role: admin"
  },
  "request": {
    "user": {"id": "root-admin", "role": "admin", "roles": ["admin"]},
    "action": "share_document",
    "resource": {"resource_type": "document", "resource_id": "doc-1"},
    "context": {}
  }
}
```

Example request:

```bash
curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "simulate": {
      "policy_change": "allow:\n  action: share_document\n  priority: 1\n  policy_key: share-admin\n  when:\n    role: admin"
    },
    "request": {
      "user": {"id": "root-admin", "role": "admin", "roles": ["admin"]},
      "action": "share_document",
      "resource": {"resource_type": "document", "resource_id": "doc-1"},
      "context": {}
    }
  }' | jq .
```

Example response:

```json
{
  "data": {
    "decision_before": {
      "allowed": false,
      "decision": "deny",
      "reason": "no matching policy",
      "policy_id": null
    },
    "decision_after": {
      "allowed": true,
      "decision": "allow",
      "reason": "policy change grants access",
      "policy_id": "share-admin"
    }
  },
  "meta": {"request_id": "...", "limit": null, "next_cursor": null, "extra": {}},
  "error": null
}
```

Common use cases:

- Review policy change impact during PRs
- Safety-check production policy updates

---

## POST /impact-analysis

Purpose:

- Estimate which users gain or lose access from a proposed policy change.

Code path:

- Route: `keynetra/api/routes/simulation.py::impact_analysis`
- Analyzer: `ImpactAnalyzer.analyze_policy_change(...)`
- Compares `before_engine` and `after_engine` decisions per user/resource candidate

Request body:

```json
{
  "policy_change": "deny:\n  action: export_payment\n  priority: 1\n  policy_key: deny-export-contractors\n  when:\n    role: external"
}
```

Example request:

```bash
curl -s -X POST http://localhost:8000/impact-analysis \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "policy_change": "deny:\n  action: export_payment\n  priority: 1\n  policy_key: deny-export-contractors\n  when:\n    role: external"
  }' | jq .
```

Example response:

```json
{
  "data": {
    "gained_access": [101, 204],
    "lost_access": [302]
  },
  "meta": {"request_id": "...", "limit": null, "next_cursor": null, "extra": {}},
  "error": null
}
```

Common use cases:

- Change approvals for security/governance
- Alerting on high-impact policy changes

---

## Errors to expect

- `401 unauthorized`: missing/invalid API key or token
- `403 forbidden`: principal lacks required management role
- `422 validation_error`: payload format or values are invalid
- `429 too_many_requests`: rate limit exceeded
- `500 database_error`: storage issue
