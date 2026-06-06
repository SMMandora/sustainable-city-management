# ADR 0001 — Data model

Date: 2026-06-02
Status: Accepted

## Context

We ingest live data from three public APIs (DublinBikes, Sonitus, OpenWeather)
and need to store both the raw payloads (for audit + replay) and the validated
domain entities (stations, sensors, observations). The hot read paths are
"last 24h of observations for one station/sensor" and "5-min buckets over the
last day."

Volume at v1: ~200 stations + sensors × 1 poll/min × 30 days ≈ 9M rows/month.
That's well within vanilla Postgres' comfort zone.

## Decision

Vanilla **PostgreSQL 16**, no TimescaleDB. Schema:

- **Dimension tables**: `DataSource`, `BikeStation`, `NoiseSensor`. Slowly-
  changing, low cardinality; upserted on each poll keyed by
  `(source, external_id)`.
- **Fact tables**: `BikeAvailability`, `NoiseReading`, `WeatherObservation`.
  Append-only time-series with `UniqueConstraint(station, observed_at)` (or
  equivalent) for idempotency.
- **Audit**: `RawPayload` stores every fetched response body for 7 days,
  truncated by a Beat task. Enables replay after a validator change.
- **Dead letter**: `DeadLetter` captures records that fail validation,
  parsing, or persistence, preserving the original record + pydantic errors
  for forensic + manual replay.

Indexes the hot queries depend on:

- `(station_id, -observed_at)` and `(-observed_at)` on each fact table.
- Bucket aggregation uses Postgres native `date_bin(INTERVAL '5 minutes',
  observed_at, TIMESTAMP '2000-01-01')` in a selector function — no
  materialized view at MVP volumes.

## Alternatives considered

**TimescaleDB.** Continuous aggregates and time partitioning would let us scale
to ~100M+ rows comfortably. But it requires a non-standard Postgres image,
breaks vanilla compose + CI testcontainers, and yields no measurable benefit at
the v1 volume. Decision: defer; revisit if retention crosses ~100M rows.

**One mega fact table** (polymorphic observations). Would simplify cross-source
queries but lose Postgres' type-safe constraints. Rejected — readability and
constraint enforcement worth the duplication.

**Storing only validated data, no raw audit table.** Cheaper but means a
validator bug silently corrupts history. Rejected — the 7-day audit window
gives us a recovery path.

## Consequences

- The `RawPayload` + `DeadLetter` pair means ingestion is forensic by default:
  no record is ever silently dropped.
- Idempotency is enforced at the DB layer via unique constraints, so re-running
  yesterday's poll is safe even after a worker crash.
- Vanilla Postgres means `docker compose up` and CI `services:` blocks work
  with no extra plumbing.
