# Authorization Models

If you are new to authorization, this is the quickest mental model:

- RBAC answers: "What can this role do?"
- ABAC answers: "Do attributes satisfy policy conditions?"
- ACL answers: "Is this exact user/group explicitly allowed or denied on this resource?"
- ReBAC answers: "Does a relationship path grant access?"

KeyNetra supports all four and can combine them in a single decision.

## How to choose

- Start with RBAC for coarse permissions
- Add ABAC for dynamic constraints (department, time, amount)
- Add ACL for exceptions on specific resources
- Add ReBAC for sharing/collaboration graphs (owner/editor/member)

## Example model (document system)

```yaml
model:
  type: document
  relations:
    owner: user
    editor: user
    viewer: user
  permissions:
    read: owner or editor or viewer
    write: owner or editor
    delete: owner
```

## Read next

- [RBAC](rbac.md)
- [ABAC](abac.md)
- [ACL](acl.md)
- [ReBAC](rebac.md)
