# Roadmap

## 2026 H1
- Harden production defaults and configuration safety checks.
- Expand CI quality gates: typing, security scans, contract drift, load smoke budgets.
- Introduce policy lifecycle states (`draft`, `active`, `archived`) with canary evaluation.

## 2026 H2
- Add first-class OpenFGA and OPA/Rego adapters.
- Publish Terraform provider for policy resources.
- Expand async data-path options for higher-concurrency deployments.

## Backlog
- Deeper mutation testing strategy for policy/rule evaluation.
- Per-tenant async worker model and queue-based authorization batch processing.
- Additional policy authoring UX and governance tooling.
