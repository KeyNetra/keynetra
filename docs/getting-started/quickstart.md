---
title: Quickstart
---

# Quickstart

This guide validates a full local KeyNetra flow: install, run server, execute a decision request, and inspect results.

## Prerequisites

- Python 3.11+
- `pip`
- `curl`
- Optional: `jq` for pretty JSON output

## 1. Install Dependencies

From repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## 2. Configure API Access Key

```bash
export KEYNETRA_API_KEYS=devkey
```

Optional but useful for first run:

```bash
export KEYNETRA_ENVIRONMENT=development
export KEYNETRA_AUTO_SEED_SAMPLE_DATA=true
```

## 3. Start the API Server

```bash
python -m keynetra.cli serve --host 0.0.0.0 --port 8000
```

Server entrypoint is `keynetra/api/main.py` and default URL is `http://localhost:8000`.

## 4. Verify Health and Readiness

```bash
curl -s http://localhost:8000/health | jq .
curl -s http://localhost:8000/health/ready | jq .
```

Expected status is `ok` for healthy local setup.

## 5. Run Your First Access Decision

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

Key fields to review in the response:

- `data.allowed`: final allow/deny boolean
- `data.decision`: normalized decision string
- `data.matched_policies`: rules that produced the outcome
- `request_id`: request correlation id from middleware

## 6. Run a Batch Check

```bash
curl -s -X POST http://localhost:8000/check-access-batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "user": {"id": "alice", "role": "manager"},
    "items": [
      {
        "action": "read",
        "resource": {"resource_type": "document", "resource_id": "doc-1"},
        "context": {}
      },
      {
        "action": "delete",
        "resource": {"resource_type": "document", "resource_id": "doc-1"},
        "context": {}
      }
    ]
  }' | jq .
```

Use this endpoint when a single user needs multiple action checks in one network call.

## 7. Simulate a Policy Change

```bash
curl -s -X POST http://localhost:8000/simulate-policy \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -d '{
    "simulate": {
      "policy_change": "allow:\n  action: read\n  priority: 10\n  when:\n    role: admin"
    },
    "request": {
      "user": {"id": "u1", "role": "admin"},
      "action": "read",
      "resource": {"resource_type": "document", "resource_id": "doc-1"},
      "context": {}
    }
  }' | jq .
```

This lets you validate policy behavior before persisting the change.

## 8. Stop the Server

Use `Ctrl+C` in the terminal running `serve`.

## Next Steps

- [Runtime Modes](runtime-modes.md)
- [API Reference](../reference/api-reference.md)
- [CLI Reference](../reference/cli-reference.md)
- [End-to-End API Example](../examples/end-to-end-api-flow.md)
