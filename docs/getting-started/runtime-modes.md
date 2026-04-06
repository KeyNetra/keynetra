---
title: Runtime Modes
---

# Runtime Modes

KeyNetra can run in three modes.

## 1) API server mode

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve
```

Use when other services call authorization over HTTP.

## 2) CLI mode

```bash
python -m keynetra.cli check \
  --api-key devkey \
  --user '{"id":"alice","role":"manager"}' \
  --action approve_payment \
  --resource '{"resource_type":"payment","resource_id":"pay-900","amount":5000}'
```

Use for local testing, scripts, and operations.

## 3) Embedded Python mode

```python
from keynetra import KeyNetra

engine = KeyNetra.from_config("./keynetra.yaml")
decision = engine.check_access(
    subject="user:alice",
    action="read",
    resource="document:doc-1",
    context={}
)
print(decision.allowed)
```

Use when you want in-process authorization in Python applications.
