# CLI Reference

The public CLI entrypoint is `keynetra`.

## Global Options

```bash
keynetra --help
keynetra --config examples/keynetra.yaml <command>
```

## Core Commands

```bash
keynetra version
keynetra serve --host 127.0.0.1 --port 8080
keynetra start --host 0.0.0.0 --port 8000
keynetra help-cli
keynetra migrate --confirm-destructive
keynetra seed-data
keynetra purge-idempotency
```

## Authorization Commands

```bash
keynetra check \
  --api-key devkey \
  --action read \
  --user '{"id":"u1"}' \
  --resource '{"resource_type":"document","resource_id":"doc-1"}'

keynetra explain --user u1 --resource document:doc-1 --action read
keynetra benchmark --api-key devkey
```

## Policy Commands

```bash
keynetra compile-policies --path examples/policies
keynetra test-policy examples/policy_tests.yaml
keynetra generate-openapi --output docs/openapi.json
keynetra check-openapi --contract docs/openapi.json
keynetra doctor --service core
```

## ACL Commands

```bash
keynetra acl add --subject-type user --subject-id u1 --resource-type document --resource-id doc-1 --action read --effect allow
keynetra acl list --resource-type document --resource-id doc-1
keynetra acl remove --acl-id 1
```

## Model Commands

```bash
keynetra model apply examples/auth-model.yaml --api-key devkey
keynetra model show --api-key devkey
```

## Notes

- `start` is a backward-compatible alias for `serve`.
- `generate-openapi` writes files through `--output` and `--yaml-output`; it does not stream the contract to stdout.
- Use `keynetra help-cli` for the repository-maintained quick reference.
