# Docker Deploy

Docker assets:

- `deploy/docker/Dockerfile`
- `deploy/docker/docker-compose.yml`

## Local Docker Compose

From repository root:

```bash
docker compose -f deploy/docker/docker-compose.yml up --build
```

Default compose setup expects:

- API on `http://localhost:8000`
- Postgres/Redis services from `deploy/docker/docker-compose.yml`

## Minimal Environment Example

```env
KEYNETRA_DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/keynetra
KEYNETRA_REDIS_URL=redis://redis:6379/0
KEYNETRA_API_KEYS=devkey
KEYNETRA_API_KEY_SCOPES_JSON={"devkey":{"tenant":"default","role":"admin","permissions":["*"]}}
KEYNETRA_JWT_SECRET=replace-with-strong-secret
KEYNETRA_ENVIRONMENT=prod
KEYNETRA_STRICT_TENANCY=true
```

## Scale API Replicas

```bash
docker compose -f deploy/docker/docker-compose.yml up --scale keynetra=3
```

Use a reverse proxy/load balancer in front of replicas for production traffic.
