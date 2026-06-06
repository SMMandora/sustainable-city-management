# Architecture

```
                              ┌──────────────────────────────┐
                              │       Public APIs            │
                              │  DublinBikes (GBFS)          │
                              │  Sonitus (auth required)     │
                              │  OpenWeather (Dublin)        │
                              └──────────────┬───────────────┘
                                             │ httpx GET (every 60s)
                                             ▼
                              ┌──────────────────────────────┐
                              │  Ingestion (Celery worker)   │
                              │  ┌────────────────────────┐  │
                              │  │ pipeline.process       │  │
                              │  │ 1. save RawPayload     │  │
                              │  │ 2. validate envelope   │  │
                              │  │ 3. validate each rec → │──┼─► DeadLetter (audit)
                              │  │    pydantic v2         │  │
                              │  │ 4. upsert (idempotent) │  │
                              │  │ 5. send_event SSE      │  │
                              │  └────────────────────────┘  │
                              │   Redis-backed pybreaker     │
                              │   tenacity exponential retry │
                              └──────────┬──────────┬────────┘
                                         │          │
                          ┌──────────────▼──┐    ┌──▼────────────────┐
                          │ Postgres 16     │    │ Redis 7           │
                          │  · dimensions   │    │  · Celery broker  │
                          │  · facts (time- │    │  · pybreaker state│
                          │    series)      │    │  · channel layer  │
                          │  · raw payload  │    │  · SSE pub/sub    │
                          │  · dead letter  │    │  · cache          │
                          └──────────┬──────┘    └──┬────────────────┘
                                     │              │
                          ┌──────────▼──────────────▼─────┐
                          │   Django web (ASGI, gunicorn  │
                          │   + uvicorn workers)          │
                          │  ┌─────────────────────────┐  │
                          │  │ /api/v1/  (DRF)         │  │
                          │  │ /api/v1/stream/<topic>  │  │
                          │  │ /api/schema/  (OpenAPI) │  │
                          │  │ /healthz /readyz        │  │
                          │  │ /metrics (Prometheus)   │  │
                          │  └─────────────────────────┘  │
                          └──────────────┬────────────────┘
                                         │
                                         │ HTTP + SSE
                                         ▼
                          ┌──────────────────────────────┐
                          │  nginx (frontend container)  │
                          │  serves React SPA, reverse-  │
                          │  proxies /api → web          │
                          └──────────────┬───────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │  React 18 + Vite SPA         │
                          │  · /         bike map        │
                          │  · /trends   historical      │
                          │  · /noise    sensor map      │
                          │  React Query + EventSource   │
                          │  invalidates queries on SSE  │
                          └──────────────────────────────┘
```

## Deployment topologies

**Local dev (`docker compose up`):**
- One `postgres`, one `redis`, one `web`, one `worker`, one `beat`, one
  `frontend` container.
- Frontend exposed on `:5173`, backend on `:8000`. The frontend's nginx
  reverse-proxies `/api`, `/healthz`, `/readyz`, `/metrics` to `web:8000`.

**Local staging (`just kind-up && just deploy-staging`):**
- kind cluster with nginx-ingress.
- Same containers as compose, but each backend role gets its own Deployment.
- `web` runs 2 replicas with HPA targeting CPU 70% (max 6).
- `worker` runs 2 replicas, fixed.
- `beat` runs 1 replica, `strategy: Recreate` (must be singleton).
- `postgres` + `redis` as StatefulSets with 1Gi / 512Mi PVCs.
- Two Ingresses share `scm.localtest.me`: a default one for REST, plus a
  streaming-friendly one for `/api/v1/stream` with `proxy-buffering: off`.

## Why these choices

See:
- [ADR 0001 — Data model](adr/0001-data-model.md)
- [ADR 0002 — Ingestion strategy](adr/0002-ingestion-strategy.md)
- [ADR 0003 — API versioning](adr/0003-api-versioning.md)
