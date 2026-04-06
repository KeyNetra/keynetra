---
title: Authorization Model Files
---

# Authorization Model Files

Authorization schema model support is implemented in:

- `keynetra/config/file_loaders.py`
- `keynetra/modeling/schema_parser.py`
- `keynetra/modeling/model_validator.py`
- `keynetra/modeling/permission_compiler.py`

Supported file formats:

- `.yaml` / `.yml`
- `.json`
- `.toml`
- `.schema` / `.txt` (raw schema DSL)

These files define relation and permission semantics used by the schema permission stage in authorization evaluation.

## YAML Example

```yaml
model:
  schema_version: 1
  type: document
  relations:
    owner: user
    editor: user
  permissions:
    read: owner or editor
    write: owner
```

## Generated DSL Shape

Files are normalized to schema DSL with sections like:

```text
model schema 1
type user
type document
relations
owner: [user]
editor: [user]
permissions
read = owner or editor
write = owner
```

## Runtime Integration

- API startup auto-load via configured `model_paths`.
- `POST /auth-model` stores and compiles model per tenant.
- Embedded usage via `KeyNetra.load_model(...)`.

## Minimal DSL Example

```text
model schema 1
type user
type document
relations
owner: [user]
permissions
read = owner
```

## Validation Rules

The compiler/validator enforces:

- schema version must be `>= 1`
- at least one type and permission must exist
- `user` type must exist
- relation subjects must reference defined types
- permission expressions must reference known relations/permissions

## Related Pages

- [Configuration Files](configuration-files.md)
- [Authorization Pipeline](../architecture/authorization-pipeline.md)
- [API Reference](api-reference.md)
- [Policy File Formats](policy-files.md)
