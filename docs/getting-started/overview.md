---
title: Project Overview
---

# Project Overview

KeyNetra is a Python authorization platform that combines a deterministic policy engine with API, CLI, and embedded usage modes.

It is designed for self-hosted, headless-first deployments where policy evaluation must remain deterministic and auditable.

## Repository Scope

Primary implementation lives in:

- `keynetra/engine`: pure authorization engine
- `keynetra/services`: orchestration layer for policy loading, cache, audit, and resilience
- `keynetra/api`: FastAPI transport and middleware
- `keynetra/infrastructure`: DB/cache repositories, logging, and metrics integrations
- `keynetra/domain`: SQLAlchemy models and Pydantic schemas
- `keynetra/config`: settings, security, tenancy, and config file loading
- `alembic/`: database migrations
- `infra/`: Docker and Kubernetes deployment assets
- `contracts/openapi/keynetra-v0.1.0.yaml`: OpenAPI contract
- `examples/`: config, policy, and model examples

## Core Capabilities

- RBAC: users, roles, permissions, and role-permission binding
- ACL: resource-level allow/deny entries
- ReBAC: relationship graph checks
- ABAC-style policies: compiled decision graph from policy definitions
- Authorization modeling: schema parser, validator, and permission compiler
- Policy simulation and impact analysis
- Revision and consistency controls
- Redis-backed distributed cache with in-memory fallback
- Prometheus metrics and structured logging

## Usage Modes

KeyNetra supports three primary operating modes:

- HTTP API server mode
- CLI operational mode
- Embedded engine mode inside Python applications

See [Runtime Modes](runtime-modes.md) for concrete examples.

## Who This Is For

- Platform/backend engineers embedding authorization in services
- DevOps/SRE operators deploying KeyNetra in Docker or Kubernetes
- Application teams integrating with management and decision APIs

## Related Pages

- [Runtime Modes](runtime-modes.md)
- [Example Files](../examples/example-files.md)
- [System Architecture](../architecture/system-architecture.md)
- [API Reference](../reference/api-reference.md)
- [Docker Deployment](../operations/deployment-docker.md)
