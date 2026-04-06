---
title: CLI Workflows
---

# CLI Workflows

This page provides operational CLI recipes for development and release workflows.

## Local Bootstrap

```bash
python -m keynetra.cli migrate
python -m keynetra.cli seed-data --reset
python -m keynetra.cli serve
```

## API Decision via CLI

```bash
python -m keynetra.cli check \
  --api-key devkey \
  --user '{"id":"alice","role":"manager"}' \
  --action approve_payment \
  --resource '{"resource_type":"payment","resource_id":"pay-900","amount":5000}'
```

## Policy Validation Pipeline

```bash
python -m keynetra.cli compile-policies --config docs/examples/assets/keynetra.yaml
python -m keynetra.cli test-policy docs/examples/assets/policy_tests.yaml
python -m keynetra.cli doctor --service core --config docs/examples/assets/keynetra.yaml
```

## Runtime Debug Flow

```bash
python -m keynetra.cli explain \
  --user u1 \
  --resource doc-1 \
  --action read \
  --context '{"department":"finance"}'
```

## Performance Smoke Test

```bash
python -m keynetra.cli benchmark \
  --url http://localhost:8000/check-access \
  --requests 200 \
  --concurrency 20 \
  --api-key devkey
```

## ACL Maintenance

```bash
python -m keynetra.cli acl add \
  --subject-type user \
  --subject-id alice \
  --resource-type document \
  --resource-id doc-1 \
  --action read \
  --effect allow

python -m keynetra.cli acl list --resource-type document --resource-id doc-1
python -m keynetra.cli acl remove --acl-id 1
```

## Related Pages

- [CLI Reference](../reference/cli-reference.md)
- [Quickstart](../getting-started/quickstart.md)
