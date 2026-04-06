---
title: CLI Reference
---

# CLI Reference

KeyNetra CLI is implemented in `keynetra/cli.py` and built with Typer.

Entrypoint:

```bash
python -m keynetra.cli --help
```

## Global Option

- `--config <path>`: load YAML/JSON/TOML configuration before executing a command.

## Command Summary

Server and runtime:

- `serve`
- `start` (backward-compatible alias)
- `version`
- `help-cli`

Auth and operations:

- `admin-login`
- `migrate`
- `seed-data`
- `doctor`

Decision workflows:

- `check`
- `simulate`
- `impact`
- `explain`
- `benchmark`

Policy/model tooling:

- `test-policy`
- `compile-policies`
- `model apply`
- `model show`

ACL tooling:

- `acl add`
- `acl list`
- `acl remove`

## Core Workflows

### Start server

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve --host 0.0.0.0 --port 8000
```

### Check one access request

```bash
python -m keynetra.cli check \
  --api-key devkey \
  --user '{"id":"alice","role":"manager"}' \
  --action approve_payment \
  --resource '{"resource_type":"payment","resource_id":"pay-900","amount":5000}' \
  --context '{"department":"finance"}'
```

### Simulate a policy change before rollout

```bash
python -m keynetra.cli simulate \
  --api-key devkey \
  --policy-change 'allow:\n  action: read\n  priority: 10\n  policy_key: read-admin\n  when:\n    role: admin' \
  --user '{"id":"u1","role":"admin"}' \
  --action read \
  --resource '{"resource_type":"document","resource_id":"doc-1"}'
```

### Estimate policy impact

```bash
python -m keynetra.cli impact \
  --api-key devkey \
  --policy-change 'deny:\n  action: export_payment\n  priority: 5\n  policy_key: deny-export-external\n  when:\n    role: external'
```

### Compile policies from configured paths

```bash
python -m keynetra.cli compile-policies --config docs/examples/assets/keynetra.yaml
```

### Validate policy tests

```bash
python -m keynetra.cli test-policy docs/examples/assets/policy_tests.yaml
```

### Local readiness checks

```bash
python -m keynetra.cli doctor --service core --config docs/examples/assets/keynetra.yaml
```

## Model Commands

Apply a schema model:

```bash
python -m keynetra.cli model apply docs/examples/assets/auth-model.yaml --api-key devkey
```

Read current model:

```bash
python -m keynetra.cli model show --api-key devkey
```

## ACL Commands

Add ACL:

```bash
python -m keynetra.cli acl add \
  --subject-type user \
  --subject-id alice \
  --resource-type document \
  --resource-id doc-1 \
  --action read \
  --effect allow
```

List ACL for resource:

```bash
python -m keynetra.cli acl list --resource-type document --resource-id doc-1
```

Remove ACL entry:

```bash
python -m keynetra.cli acl remove --acl-id 1
```

## Exit Behavior

- Commands raise non-zero exit code on HTTP failure, validation failure, or readiness failure.
- `test-policy` exits non-zero if any policy test fails.
- `doctor` exits non-zero when `ok=false`.

## Related Pages

- [Quickstart](../getting-started/quickstart.md)
- [API Reference](api-reference.md)
- [Policy File Formats](policy-files.md)
- [CLI Workflows](../examples/cli-workflows.md)
