# CLI Guide

KeyNetra CLI lets you run and validate authorization without UI.

Main entry point:

```bash
python -m keynetra.cli --help
```

## Start server

```bash
export KEYNETRA_API_KEYS=devkey
python -m keynetra.cli serve
```

## Load models

Apply a model file to API:

```bash
python -m keynetra.cli model apply ./path/to/auth-model.yaml --api-key devkey
```

Show current model:

```bash
python -m keynetra.cli model show --api-key devkey
```

## Run access checks

```bash
python -m keynetra.cli check \
  --api-key devkey \
  --user '{"id":"alice","role":"manager"}' \
  --action approve_payment \
  --resource '{"resource_type":"payment","resource_id":"pay-900","amount":5000}' \
  --context '{"department":"finance"}'
```

## Simulate policy changes

```bash
python -m keynetra.cli simulate \
  --api-key devkey \
  --policy-change 'allow:\n  action: share_document\n  priority: 1\n  policy_key: share-admin\n  when:\n    role: admin' \
  --user '{"id":"root-admin","role":"admin","roles":["admin"]}' \
  --action share_document \
  --resource '{"resource_type":"document","resource_id":"doc-1"}'
```

## Run impact analysis

```bash
python -m keynetra.cli impact \
  --api-key devkey \
  --policy-change 'deny:\n  action: export_payment\n  priority: 1\n  policy_key: deny-export-contractors\n  when:\n    role: external'
```

## Helpful developer commands

```bash
python -m keynetra.cli test-policy ./path/to/policy_tests.yaml
python -m keynetra.cli compile-policies --path ./policies
python -m keynetra.cli explain --user alice --resource doc-1 --action read
python -m keynetra.cli doctor --service core
python -m keynetra.cli version
```
