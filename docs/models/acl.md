# ACL (Access Control List)

ACL stores explicit allow/deny entries per resource.

## Simple idea

You can override generic rules for one resource.

Example entry:

```json
{
  "subject_type": "user",
  "subject_id": "charlie",
  "resource_type": "document",
  "resource_id": "doc-1",
  "action": "share",
  "effect": "deny"
}
```

## When ACL is useful

- One-off exceptions
- Sensitive records requiring explicit grants/denies
- Temporary access overrides

## Caution

Avoid relying only on ACL for large systems. Combine with RBAC/ABAC.
