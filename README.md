# Sustainable City Management

Real-time data platform for Dublin city infrastructure. Ingests live data from
DublinBikes, Sonitus noise sensors, and OpenWeather; serves it via REST + SSE;
renders three live React dashboards.

Public dashboards, no auth.

## Stack

Django 5 + DRF + Celery + PostgreSQL 16 + Redis 7 on the backend. React 18 +
Vite + Leaflet + Recharts on the frontend. Local kind/k3d for K8s staging.
GitHub Actions for CI/CD. Grafana + Prometheus + structured JSON logging for
observability.

## Quickstart

Prereqs: Docker Desktop, `just` ([install](https://github.com/casey/just)),
`uv` ([install](https://docs.astral.sh/uv/getting-started/installation/)),
Node 20+, Python 3.12.

```sh
just setup        # install Python + Node deps
just up           # docker compose up -d (postgres, redis, web, worker, beat)
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

The Django admin lives at `http://localhost:8000/admin/`. The API is mounted at
`/api/v1/` and the OpenAPI schema at `/api/schema/`.

## Layout

```
services/backend/    Django project + apps (single project, multiple apps)
frontend/            Vite + React SPA
deploy/              docker-compose, K8s manifests, Grafana, Prometheus
docs/                Architecture diagram, ADRs, runbook
tests/               integration, contract, e2e, load (unit tests live next to apps)
```

See [`docs/adr/`](docs/adr/) for the data-model, ingestion-strategy, and
API-versioning decisions. See [`docs/runbook.md`](docs/runbook.md) for incident
response.

## Common tasks

```sh
just test          # pytest (unit + integration locally)
just test-cov      # pytest with coverage
just lint          # ruff + ruff-format check
just typecheck     # mypy --strict
just e2e           # Playwright against local compose stack
just load-test     # k6 against /api/v1/bike-availability
just kind-up       # spin up local kind cluster
just deploy-staging  # kubectl apply -k deploy/k8s/overlays/kind
```

## Local K8s staging

Mirrors the production topology on a local [kind](https://kind.sigs.k8s.io/)
cluster behind nginx-ingress at `http://scm.localtest.me`.

```sh
just kind-up          # create cluster + install nginx-ingress
just kind-load        # build images + load into kind's local cache

# Create real secrets (do not commit):
kubectl create secret generic scm-secrets -n scm \
  --from-literal=django-secret-key="$(openssl rand -hex 32)" \
  --from-literal=postgres-password='postgres' \
  --from-literal=openweather-api-key='<your-key>' \
  --from-literal=sonitus-username='' \
  --from-literal=sonitus-password=''

just deploy-staging   # kubectl apply -k deploy/k8s/overlays/kind
```

See [`docs/architecture.md`](docs/architecture.md) for the data flow diagram
and ADRs in [`docs/adr/`](docs/adr/) for the data-model, ingestion-strategy,
and API-versioning decisions.

## Status

Built incrementally in 8 phases. Track progress in the plan file under
`.claude/plans/`.
