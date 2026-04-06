# KeyNetra Documentation

This documentation set is organized like an OSS project handbook: quick onboarding, architecture references, operations runbooks, and executable examples.

## Recommended Reading Order

1. [Project Overview](getting-started/overview.md)
2. [Installation](getting-started/installation.md)
3. [Quickstart](getting-started/quickstart.md)
4. [Example Files](examples/example-files.md)
5. [API Reference](reference/api-reference.md)

## Documentation Map

Getting Started:

- [Overview](getting-started/overview.md)
- [Installation](getting-started/installation.md)
- [Quickstart](getting-started/quickstart.md)
- [Runtime Modes](getting-started/runtime-modes.md)

Examples:

- [Example Files](examples/example-files.md)
- [End-to-End API Flow](examples/end-to-end-api-flow.md)
- [CLI Workflows](examples/cli-workflows.md)
- [Policy Patterns](examples/policy-patterns.md)

Core Concepts:

- [Authorization Models](core-concepts/authorization-models.md)
- [Request Evaluation Lifecycle](core-concepts/request-evaluation-lifecycle.md)
- [Consistency and Revisions](core-concepts/consistency-and-revisions.md)

Architecture:

- [System Architecture](architecture/system-architecture.md)
- [Authorization Pipeline](architecture/authorization-pipeline.md)
- [Caching and Consistency](architecture/caching-and-consistency.md)
- [Data Models](architecture/data-models.md)

Reference:

- [API Reference](reference/api-reference.md)
- [CLI Reference](reference/cli-reference.md)
- [Configuration Files](reference/configuration-files.md)
- [Environment Variables](reference/environment-variables.md)
- [Policy File Formats](reference/policy-files.md)
- [Authorization Model Files](reference/auth-model-files.md)

Operations:

- [Docker Deployment](operations/deployment-docker.md)
- [Kubernetes Deployment](operations/deployment-kubernetes.md)
- [Observability](operations/observability.md)
- [Security](operations/security.md)
- [Troubleshooting](operations/troubleshooting.md)

Development:

- [Local Development](development/local-development.md)
- [Migrations](development/migrations.md)
- [Testing](development/testing.md)
- [CI/CD and Release](development/ci-cd-release.md)
- [Contributing](development/contributing.md)

## Source of Truth

When documentation and code diverge, use implementation in `keynetra/` and contracts in `contracts/openapi/` as source of truth.
