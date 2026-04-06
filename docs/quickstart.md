# 5-Minute Quickstart

This quickstart is designed for developers who have never used an authorization engine.

## What you will do

1. Start KeyNetra locally
2. Send one access request
3. Read the decision and reason

## Prerequisites

- Python 3.11
- `curl`

## 1) Install and activate environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## 2) Set an API key and start server

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve
```

Server runs on `http://localhost:8000`.

## 3) Check health

```bash
curl -s http://localhost:8000/health | jq .
```

Expected shape:

```json
{
  "data": {"status": "ok"},
  "meta": {"request_id": "..."},
  "error": null
}
```

## 4) Run first authorization check

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

Typical response fields:

- `data.allowed`: `true` or `false`
- `data.decision`: `allow` or `deny`
- `data.reason`: human-readable reason
- `data.policy_id`: policy that made the decision
- `data.explain_trace`: decision trace for debugging
- `data.revision`: revision token for consistency

## 5) Run a batch check

```bash
curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "alice", "role": "manager", "permissions": ["approve_payment"]},
    "items": [
      {"action": "approve_payment", "resource": {"resource_type": "payment", "resource_id": "pay-900", "amount": 1000}},
      {"action": "delete", "resource": {"resource_type": "payment", "resource_id": "pay-900"}}
    ]
  }' | jq .
```

## Next

- [API Endpoints](api-endpoints.md)
- [Authorization Models](models/README.md)
- [Policies](policies.md)
- [CLI Guide](cli.md)
