# ADR 0002 — Ingestion strategy

Date: 2026-06-02
Status: Accepted

## Context

Three live data sources, each polled every 60 seconds. We need:

- Retry on transient upstream failures (5xx, timeouts, 429)
- Fail-fast + dead-letter on non-transient failures (4xx, malformed payloads)
- A circuit breaker so a flapping upstream doesn't thundering-herd retry forever
- Idempotency — re-running a poll cycle must not duplicate rows
- A generic enough pipeline that adding a fourth source is mechanical, not a
  refactor

## Decision

**Single generic `poll_source(source_slug)` Celery task** dispatched by Celery
Beat once per minute per source. The task looks the source up in a registry of
`SourceConfig` (client class, ordered list of `FeedConfig`s).

Each `FeedConfig` has:
- `envelope_schema` — pydantic v2 schema for the full HTTP response
- `record_schema` — pydantic v2 schema per record within
- `records_extractor` — callable that pulls the list of raw records out of the
  JSON body (e.g. `body["data"]["stations"]` for GBFS, `[body]` for OpenWeather)
- `persister` — source-specific function that upserts validated records and
  produces an `{"upserted": n}` summary
- `sse_topic` — channel to publish a delta event on after a successful persist

**Pipeline flow** (`apps/ingestion/pipeline.py`):
1. Save the raw response bytes as `RawPayload` first, even if parsing fails.
2. Validate the envelope; on `ValidationError` → dead-letter, stop.
3. Extract records; on `KeyError`/`AttributeError` → dead-letter, stop.
4. Validate each record. Failures dead-letter that single record with its
   pydantic errors; the rest of the batch proceeds.
5. Persister upserts via Django's `bulk_create(update_conflicts=True,
   unique_fields=[...])` keyed on the natural key `(source, external_id,
   observed_at)`.
6. If anything was upserted and `sse_topic` is set, publish a delta event.

**Retry + circuit breaker:**
- `tenacity`-style retry baked into the Celery task: `autoretry_for=
  (TransientError,)`, exponential backoff with jitter, max 5 retries.
- `pybreaker` with **Redis-backed `CircuitRedisStorage`** so the breaker state
  is shared across all worker processes. `fail_max=5, reset_timeout=300`.
- The HTTP client raises `TransientError` for 5xx/429/timeouts, `NonTransientError`
  for 4xx — clean classification at the boundary, not in the task.

## Alternatives considered

**One task per source.** Less indirection but means adding a source = new task
+ new Beat schedule entry + new test fixture. Rejected — the registry pattern
trivializes adding a source.

**`asgiref.sync.async_to_sync` + httpx async**. Negligible benefit for a 60s
polling cadence; not worth the asyncio complexity in a Celery sync worker.
Decision: stay sync.

**In-memory circuit breaker.** Per-process state means a flapping upstream
trips the breaker on one worker but not the others, defeating the purpose. The
Redis-backed storage is essential for correctness with `replicas>1`.

## Consequences

- Adding a source is: write client, write pydantic schemas, write persister,
  register in `SOURCES`, enable in fixture. The pipeline, retry, breaker, and
  dead-letter behavior come for free.
- The dead-letter table doubles as a manual replay queue: after fixing a
  validator, walk dead letters with `stage="validation"`, re-run them through
  the relevant `record_schema`.
- The Redis-backed breaker means a worker pod restart doesn't reset the
  failure count — a misbehaving upstream stays broken-circuited until the
  reset timeout, regardless of pod churn.
