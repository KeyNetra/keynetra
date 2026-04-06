---
title: Policy File Formats
---

# Policy File Formats

Policy file loaders are implemented in:

- `keynetra/config/file_loaders.py`

Supported policy formats:

- `.yaml` / `.yml`
- `.json`
- `.polar`

Policy files can be loaded from individual files or recursively scanned directories.

## YAML

```yaml
policies:
  - action: read
    effect: allow
    priority: 10
    policy_id: document-read-admin
    conditions:
      role: admin
```

Also supported:

```yaml
allow:
  action: read
  priority: 10
  when:
    role: admin
```

## JSON

```json
[
  {
    "action": "approve_payment",
    "effect": "allow",
    "priority": 5,
    "conditions": { "role": "manager", "max_amount": 10000 }
  }
]
```

## Polar-like Flat Rules

```text
allow action=deploy priority=15 role=ops
deny action=deploy priority=100
```

## Loading from Paths

Configured `policy_paths` can be files or directories. Directory paths are scanned recursively for supported extensions.

Priority and conditions are preserved as loaded and compiled into the decision graph.

Runtime hooks:

- CLI compile: `python -m keynetra.cli compile-policies --config ...`
- API startup bootstrap: `keynetra/api/main.py` (`_bootstrap_file_backed_policies`)
- Embedded usage: `KeyNetra.load_policies(...)`

## Validation Tips

- Ensure each rule has a non-empty `action`.
- Use explicit `priority` values for deterministic precedence.
- Keep condition keys consistent with request payload fields.

## Related Pages

- [Configuration Files](configuration-files.md)
- [Authorization Pipeline](../architecture/authorization-pipeline.md)
- [CLI Reference](cli-reference.md)
