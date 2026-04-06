# Real-World Use Cases

This page maps common product scenarios to KeyNetra concepts.

## 1) Document Management System

Typical requirements:

- Owners can read/write/delete
- Editors can read/write
- Viewers can only read
- Specific users can be denied sharing for sensitive docs

How KeyNetra helps:

- ReBAC for owner/editor/viewer relationships
- ACL for per-document exceptions
- Policy trace for support/debugging

## 2) SaaS Multi-Tenant Platform

Typical requirements:

- User can only access resources in their tenant
- Tenant admins manage tenant settings
- Cross-tenant access is denied by default

How KeyNetra helps:

- ABAC (`same_tenant`) checks
- RBAC for `tenant_admin` vs `tenant_member`
- Batch checks for dashboards with many widgets

## 3) Financial Approval Workflow

Typical requirements:

- Managers can approve up to a threshold
- Finance admins approve above threshold
- Maker-checker separation (owner cannot self-approve)

How KeyNetra helps:

- ABAC for amount-based limits
- Explicit deny for maker-checker guardrail
- `/simulate-policy` before rolling out new thresholds

## 4) Team Collaboration System

Typical requirements:

- Maintainers can merge
- Contributors can comment/read
- External users cannot merge even if they can view

How KeyNetra helps:

- ReBAC for maintainer/contributor relationships
- RBAC for external role restrictions
- ACL exceptions for temporary project access

## 5) Admin Delegation

Typical requirements:

- Root admin can delegate limited rights
- Delegated admins can grant but not perform all root operations
- Read-only support users should never mutate policy

How KeyNetra helps:

- RBAC + ABAC for delegated constraints
- ACL deny entries for protected policy operations
- Impact analysis before changing admin policies

## Suggested validation process for any use case

1. Define model relations and permissions
2. Write baseline policies
3. Add ACL exceptions only where needed
4. Run `/simulate` and `/simulate-policy`
5. Run `/impact-analysis`
6. Add tests for critical rules
