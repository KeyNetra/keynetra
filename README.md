<p align="center">
  <img src="./data/imgs/logo.png" alt="KeyNetra Logo" width="220" />
</p>
<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=18&pause=1100&center=true&vCenter=true&width=900&lines=Deterministic+Authorization+Control+Plane;RBAC+%2B+ACL+%2B+ReBAC+for+modern+apps;FastAPI+API%2C+CLI%2C+Caching%2C+Observability" alt="KeyNetra animated typing banner" />
</p>
<div align="center">

[![CI](https://github.com/keynetra/keynetra/actions/workflows/ci.yml/badge.svg)](https://github.com/keynetra/keynetra/actions/workflows/ci.yml)
[![Release](https://github.com/keynetra/keynetra/actions/workflows/release.yml/badge.svg)](https://github.com/keynetra/keynetra/actions/workflows/release.yml)
[![Docker Hub](https://img.shields.io/docker/pulls/keynetra/keynetra?label=docker%20pulls)](https://hub.docker.com/r/keynetra/keynetra)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](./pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](./LICENSE)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.1-orange)](./contracts/openapi/openapi.json)
[![Deploy](https://img.shields.io/badge/deploy-docker%20%7C%20k8s%20%7C%20helm-059669)](./DEPLOYMENT.md)
[![Security](https://img.shields.io/badge/security-policy-blue)](./SECURITY.md)

</div>

# KeyNetra

Policy-driven authorization control plane for applications that need deterministic, explainable access decisions across RBAC, ACL, and ReBAC.

## What KeyNetra Provides

- Authorization engine with deterministic evaluation and explain traces
- FastAPI API server and operational CLI
- Multi-tenant policy evaluation with strict tenancy controls
- Policy lifecycle operations (validation, compile, simulation, impact analysis)
- Caching and access indexing for low-latency checks
- Structured logging, metrics, and dashboard-ready monitoring
- Deployment assets for Docker, Kubernetes, and Helm

## Architecture

Layering is enforced through import contracts:

- `keynetra.api` -> transport only
- `keynetra.services` -> orchestration and runtime flow
- `keynetra.engine` -> pure policy decision logic
- `keynetra.domain` -> shared models/schemas
- `keynetra.infrastructure` -> repositories, storage, cache adapters
- `keynetra.config` -> configuration loading and guardrails

Detailed architecture notes: [`ARCHITECTURE.md`](./ARCHITECTURE.md)

## Quick Start (Local)

### 1) Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
pip install -e .
cp .env.example .env
```

### 2) Run API

```bash
keynetra serve --host 0.0.0.0 --port 8080
```

### 3) Health and Docs

```bash
curl -i http://localhost:8080/health/ready
open http://localhost:8080/docs
```

### 4) First Authorization Check

```bash
curl -s -X POST http://localhost:8080/check-access \
  -H "Content-Type: application/json" \
  -H "X-API-Key: devkey" \
  -H "X-Tenant-Id: acme" \
  -d '{
    "user": {"id": "u1", "role": "admin"},
    "action": "read",
    "resource": {"resource_type": "document", "resource_id": "doc-1"},
    "context": {}
  }'
```

## CLI Usage

Entrypoint is standardized to `keynetra`:

```bash
keynetra --help
keynetra check-openapi
keynetra migrate --confirm-destructive
keynetra doctor --service core
```

## API Surface (Core)

- `POST /check-access`
- `POST /check-access-batch`
- `POST /simulate`
- `POST /simulate-policy`
- `POST /impact-analysis`
- `GET /health`, `GET /health/ready`, `GET /metrics`

OpenAPI contracts:

- [`contracts/openapi/openapi.json`](./contracts/openapi/openapi.json)
- [`contracts/openapi/keynetra-v0.1.0.yaml`](./contracts/openapi/keynetra-v0.1.0.yaml)

## Multi-Tenant and Security

- Tenant-aware request flow and storage isolation
- Strict tenancy mode available via `KEYNETRA_STRICT_TENANCY=true`
- API key and JWT auth support
- Admin auth flow for privileged operations
- Rate limiting and request correlation IDs

See [`SECURITY.md`](./SECURITY.md) for security policy and reporting.

## Observability and Monitoring

KeyNetra exposes Prometheus metrics at `GET /metrics` including:

- HTTP request count/latency/error metrics
- Authorization decision and stage latency metrics
- Cache hit/miss metrics
- DB query latency metrics
- Tenant activity dimensions

Monitoring assets:

- Prometheus config: [`monitoring/prometheus/prometheus.yml`](./monitoring/prometheus/prometheus.yml)
- Grafana dashboard: [`monitoring/grafana/dashboards/keynetra-overview.json`](./monitoring/grafana/dashboards/keynetra-overview.json)
- Grafana provisioning: [`monitoring/grafana/provisioning`](./monitoring/grafana/provisioning)

## Deployment

### Docker

```bash
docker build -t keynetra:test .
docker run --rm -p 8080:8080 --env-file .env keynetra:test
```

### Docker Compose (Full Dev/Obs Stack)

```bash
docker compose up --build
```

Includes:

- KeyNetra API
- PostgreSQL
- Redis
- Prometheus
- Grafana
- node-exporter
- Loki

### Kubernetes

```bash
kubectl apply -f deploy/kubernetes/
```

### Helm

```bash
helm install keynetra ./deploy/helm/keynetra
```

More deployment detail: [`DEPLOYMENT.md`](./DEPLOYMENT.md)

## SDKs

SDKs are maintained separately from this engine repository.

- Python SDK package: `keynetra-client`
- SDK guide: [`SDK_GUIDE.md`](./SDK_GUIDE.md)

Example (Python SDK):

```python
from keynetra_client import KeyNetraClient

client = KeyNetraClient("http://localhost:8080")
decision = client.check_access(
    user={"id": "alice"},
    action="read",
    resource={"type": "document", "id": "doc-1"},
)
print(decision.allowed)
```

## Developer Workflow

```bash
ruff check .
black --check .
pytest
lint-imports --config .importlinter
```

Convenience commands are available in [`Makefile`](./Makefile).

## Documentation Index

- [`ARCHITECTURE.md`](./ARCHITECTURE.md)
- [`DEPLOYMENT.md`](./DEPLOYMENT.md)
- [`SDK_GUIDE.md`](./SDK_GUIDE.md)
- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md)
- [`SECURITY.md`](./SECURITY.md)
- [`CHANGELOG.md`](./CHANGELOG.md)
- [`docs/README.md`](./docs/README.md)

## Contributing

Contributions are welcome. Start with [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

## License

Apache-2.0. See [`LICENSE`](./LICENSE).

Made with love ❤️ for KeyNetra Community.

## Citation

```bibtex
@software{keynetra_2026,
  title   = {KeyNetra},
  author  = {KeyNetra Community},
  year    = {2026},
  version = {0.1.0-beta},
  url     = {https://github.com/keynetra/keynetra}
}
```
