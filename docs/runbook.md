# Runbook

Incident response procedures for the Sustainable City Management platform.

Everything below assumes the K8s namespace `scm` and a `kubectl` context
pointing at the right cluster. For local stuff substitute `docker compose
exec` where noted.

## Quick reference

| Symptom | Likely cause | Procedure |
|---------|--------------|-----------|
| `IngestStalled` firing | Upstream down, breaker open, Beat stuck | [Stalled ingest](#stalled-ingest) |
| `DeadLetterSpike` firing | Upstream schema drift | [Drain dead letters](#drain-dead-letters) |
| `CircuitOpen` firing | Upstream flapping or down | [Stuck circuit breaker](#stuck-circuit-breaker) |
| Bike map empty | Frontend can't reach API or DB empty | [Empty map](#empty-map) |
| SSE not updating | Buffering on ingress, or Beat dead | [SSE not updating](#sse-not-updating) |
| Postgres OOM / corruption | DB instance died | [Postgres restore](#postgres-restore-from-pg_dump) |
| Need a new key rotated | Annual rotation, or leaked secret | [Rotate API key](#rotate-api-key) |

## Stalled ingest

**Symptom**: `IngestStalled{source=...}` firing, dashboards show no fresh data.

```sh
# 1. Is the worker even processing tasks?
kubectl logs -n scm deployment/worker --tail=100 | grep -E "poll_source|HTTP"

# 2. Is Beat scheduling them?
kubectl logs -n scm deployment/beat --tail=50

# 3. Is the breaker open?
kubectl exec -n scm deployment/web -- python -c "
from apps.ingestion.circuit import get_breaker
for slug in ['dublin_bikes', 'sonitus', 'openweather']:
    b = get_breaker(slug)
    print(f'{slug}: {b.current_state} fails={b.fail_counter}')
"

# 4. Try the upstream directly from inside the cluster
kubectl exec -n scm deployment/web -- curl -fsS -m 5 \
  https://api.cyclocity.fr/contracts/dublin/gbfs/v2/gbfs.json | head -c 200
```

If upstream is reachable but the worker isn't polling, restart the worker.
If Beat is the problem, see [stalled Beat](#stalled-celery-beat).

## Drain dead letters

**Symptom**: `DeadLetterSpike` firing, the `observations_deadletter` row count
is climbing.

```sh
# Inspect the most recent ones by source
kubectl exec -n scm sts/postgres -- psql -U postgres -d scm -c "
  SELECT source_id, stage, error_type, count(*)
  FROM observations_deadletter
  WHERE failed_at > now() - interval '1 hour'
  GROUP BY 1, 2, 3
  ORDER BY count DESC
  LIMIT 10;
"

# Look at a specific failure
kubectl exec -n scm sts/postgres -- psql -U postgres -d scm -c "
  SELECT id, error_message, pydantic_errors
  FROM observations_deadletter
  WHERE source_id = 1 AND stage = 'validation'
  ORDER BY failed_at DESC LIMIT 1;
"
```

**Common cause**: upstream renamed or removed a field.

1. Fix the relevant pydantic schema in
   `services/backend/apps/ingestion/schemas/`.
2. Re-record the contract cassette:
   `rm tests/contract/cassettes/<src>_*.yaml && just test contract`.
3. Ship, deploy.
4. Replay the dead-lettered rows (next section).

## Replay from RawPayload

When you fix a validator and want to backfill the rows that previously failed:

```sh
kubectl exec -n scm deployment/web -- python manage.py shell <<'PY'
from apps.observations.models import DataSource, RawPayload, DeadLetter
from apps.ingestion.registry import SOURCES
from apps.ingestion import pipeline
import httpx, json

source = DataSource.objects.get(slug="dublin_bikes")
feed = SOURCES["dublin_bikes"].feeds[1]  # station_status

# Replay the last 5 raw payloads
for raw in RawPayload.objects.filter(source=source).order_by("-fetched_at")[:5]:
    response = httpx.Response(
        raw.response_status,
        content=json.dumps(raw.body).encode("utf-8"),
        request=httpx.Request("GET", raw.request_url),
    )
    pipeline.process(source, response, feed)
    print(f"replayed raw {raw.id}")
PY

# Mark the replayed dead letters resolved
kubectl exec -n scm sts/postgres -- psql -U postgres -d scm -c "
  UPDATE observations_deadletter
  SET resolved = true
  WHERE source_id = 1 AND failed_at > now() - interval '24 hours';
"
```

## Stuck circuit breaker

`CircuitOpen{source=X}` for >5 min. The breaker is Redis-backed; state survives
worker restarts.

```sh
# Confirm state across all workers (they share Redis-backed storage)
kubectl exec -n scm deployment/web -- python -c "
from apps.ingestion.circuit import get_breaker
b = get_breaker('dublin_bikes')
print(b.current_state, b.fail_counter)
"

# Force-close if upstream is verified healthy
kubectl exec -n scm deployment/web -- python -c "
from apps.ingestion.circuit import get_breaker
get_breaker('dublin_bikes').close()
print('breaker reset to closed')
"
```

For a prolonged outage, **disable the source** so polls become no-ops instead
of spamming the breaker:

```sh
kubectl exec -n scm sts/postgres -- psql -U postgres -d scm -c "
  UPDATE observations_datasource SET enabled = false WHERE slug = 'sonitus';
"
```

Re-enable when upstream recovers. No deploy needed.

## Empty map

The frontend shows zero markers.

```sh
# 1. Frontend serving?
curl -fsS http://scm.localtest.me/ | grep "<title>"

# 2. API reachable through ingress?
curl -fsS http://scm.localtest.me/api/v1/bike-stations/ | head -c 200

# 3. Is there data?
kubectl exec -n scm sts/postgres -- psql -U postgres -d scm -c "
  SELECT count(*) FROM observations_bikestation;
  SELECT count(*) FROM observations_bikeavailability
    WHERE observed_at > now() - interval '24 hours';
"
```

If (1) fails → frontend pod down. If (2) fails → ingress / web pod. If (1)/(2)
pass but (3) shows 0 → ingest stalled, follow that runbook.

## SSE not updating

Map renders but doesn't refresh on its own.

```sh
# 1. Is the SSE endpoint up?
timeout 10 curl -sS -N -H "Accept: text/event-stream" \
  http://scm.localtest.me/api/v1/stream/bikes | head -c 500
# Expect: padding bytes, then "event: stream-open", then "event: keep-alive"
# within ~25s, then "event: delta" within 60s.

# 2. Is the publisher firing?
kubectl logs -n scm deployment/worker --tail=200 | grep ingest.processed | tail
# Should show one line per feed per minute.

# 3. Is Redis pub/sub flowing?
kubectl exec -n scm sts/redis -- redis-cli -n 2 PUBSUB CHANNELS
# Should include "events_channel"
```

If (1) returns only the initial padding and never delivers events: nginx-ingress
buffering is on. Verify the streaming Ingress has `proxy-buffering: off` and
`proxy-read-timeout: 3600`:

```sh
kubectl get ingress -n scm scm-stream -o yaml | grep -A 3 annotations
```

If (2) shows no recent processed events: ingest stalled, separate runbook.

## Stalled Celery Beat

Beat must be a singleton. If it dies, NO polls get scheduled.

```sh
# Is exactly one pod running?
kubectl get pods -n scm -l app=beat

# Restart it (strategy: Recreate ensures no overlap)
kubectl rollout restart -n scm deployment/beat
kubectl rollout status -n scm deployment/beat --timeout=60s
```

**Never scale beat to >1.** Two beats = double-scheduled tasks = duplicate
ingest + exhausted upstream rate limits.

## Rotate API key

Example: OpenWeather key compromised. Same procedure for any key.

```sh
# 1. Mint a new key at openweathermap.org

# 2. Update the cluster secret
kubectl create secret generic scm-secrets -n scm \
  --from-literal=django-secret-key="$(kubectl get secret scm-secrets -n scm -o jsonpath='{.data.django-secret-key}' | base64 -d)" \
  --from-literal=postgres-password="$(kubectl get secret scm-secrets -n scm -o jsonpath='{.data.postgres-password}' | base64 -d)" \
  --from-literal=openweather-api-key="<new-key>" \
  --from-literal=sonitus-username="$(kubectl get secret scm-secrets -n scm -o jsonpath='{.data.sonitus-username}' | base64 -d)" \
  --from-literal=sonitus-password="$(kubectl get secret scm-secrets -n scm -o jsonpath='{.data.sonitus-password}' | base64 -d)" \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Roll the deployments so they pick up the new env var
kubectl rollout restart -n scm deployment/web deployment/worker

# 4. Verify
kubectl exec -n scm deployment/worker -- env | grep OPENWEATHER_API_KEY | head -c 30
```

Also update `services/backend/.env` in the dev environment so local docker
compose stays in sync.

## Scale workers

To handle a spike in upstream rate or more sources:

```sh
kubectl scale -n scm deployment/worker --replicas=4
# Verify in Grafana "Celery worker queue length" panel.
```

`web` autoscales via the HPA (CPU 70%). Manual override only in emergencies.

## Postgres restore from pg_dump

Take a backup:

```sh
kubectl exec -n scm sts/postgres -- pg_dump -U postgres scm > scm-$(date +%F).sql
```

Restore (DESTRUCTIVE — wipes the existing data):

```sh
kubectl exec -n scm sts/postgres -- dropdb -U postgres scm --if-exists
kubectl exec -n scm sts/postgres -- createdb -U postgres scm
cat scm-2026-06-01.sql | kubectl exec -i -n scm sts/postgres -- psql -U postgres -d scm
kubectl exec -n scm deployment/web -- python manage.py migrate
kubectl exec -n scm deployment/web -- python manage.py loaddata \
  apps/observations/fixtures/initial_sources.json
```

Then restart the web deployment to drop stale connections:

```sh
kubectl rollout restart -n scm deployment/web
```

## Adding a new data source

Walking checklist (use this when onboarding a 4th source):

1. Build `apps/ingestion/clients/<src>.py` (httpx GET, raises Transient/NonTransient).
2. Build `apps/ingestion/schemas/<src>.py` (pydantic v2 envelope + record).
3. Build `apps/ingestion/persisters/<src>.py` (bulk_create with update_conflicts).
4. Register in `apps/ingestion/registry.py:SOURCES`.
5. Add the slug to `apps/observations/fixtures/initial_sources.json`.
6. Add a beat schedule entry in `config/celery.py`.
7. Set any secret env vars in `services/backend/.env.example` AND
   `deploy/k8s/base/secret.example.yaml`.
8. Write a contract test that records a cassette and validates the schema
   against the live response.
9. Write at least one persister test verifying idempotency.
10. Deploy.

## Known limitations

### Worker-side custom metrics aren't on `web`'s `/metrics`

`scm_ingest_records_total`, `scm_circuit_breaker_state`, and
`scm_last_successful_poll_timestamp` are incremented in the **Celery worker**
process. The `/metrics` endpoint is served by the **web** process. Each
`prometheus_client` registry is per-process, so those values don't show up
on `web:8000/metrics`.

In production this is resolved one of two ways:

1. **multi-process mode**: set `PROMETHEUS_MULTIPROC_DIR=/tmp/prom-metrics`
   on both `web` and `worker` deployments and mount a shared `emptyDir`
   volume. Then `web`'s scrape sees the worker's counters.
2. **separate scrape targets**: deploy a small Prometheus exporter sidecar
   on the worker pods (or use `celery-exporter` for queue/runtime metrics
   and skip the custom counters).

For now, the `django_http_*` metrics (request rate, latency, status) are
live on `web:8000/metrics` and drive the API dashboard end-to-end.

## Useful one-liners

```sh
# Tail web logs across all replicas
kubectl logs -n scm -l app=web --all-containers --tail=200 -f

# Open Django shell on a running pod
kubectl exec -it -n scm deployment/web -- python manage.py shell

# Port-forward Grafana (if deployed)
kubectl port-forward -n scm svc/grafana 3000:3000

# Curl from inside the cluster (useful for testing internal DNS)
kubectl run -n scm --rm -it --image=curlimages/curl probe -- sh
```
