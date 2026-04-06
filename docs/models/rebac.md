# ReBAC (Relationship-Based Access Control)

ReBAC grants permissions from relationships between subjects and resources.

## Simple idea

If relationship exists, access may be allowed.

Examples:

- `user:alice` is `owner` of `document:doc-1`
- `user:bob` is `editor` of `document:doc-1`

Model permission:

```yaml
permissions:
  read: owner or editor or viewer
  write: owner or editor
```

## When ReBAC works well

- Document sharing
- Team collaboration tools
- Hierarchical organizations and graph permissions

## Benefit

ReBAC keeps sharing logic out of application code and inside explicit relationship data.
