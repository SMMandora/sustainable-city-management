# ADR 0003 — API versioning

Date: 2026-06-02
Status: Accepted

## Context

The REST API is consumed by our own React SPA and (potentially) by third-party
city dashboards. We need a clear story for evolving response shapes without
breaking integrators.

## Decision

**URL-path versioning**: every resource lives under `/api/v1/...`. The version
is part of the URL, not a header. The OpenAPI schema at `/api/schema/`
describes exactly the v1 contract.

**Breaking changes mean a new version.** v2 endpoints would live alongside v1
at `/api/v2/...`. We give v1 a deprecation window of at least 6 months after
v2 ships.

**Non-breaking changes** (adding fields, adding endpoints) happen in place on
v1. We document them in CHANGELOG.md but don't bump the version.

**pydantic ingestion schemas are kept separate from DRF serializers.** Reason:
upstream contract drift (e.g. JCDecaux renaming a field) must not force us to
change our public API shape. Ingestion schemas validate the upstream wire
format; DRF serializers project our internal models to our public API.

**Conventions baked into v1:**
- Time windows: `since` inclusive, `until` exclusive, half-open `[since, until)`.
  Documented in OpenAPI globally.
- Datetimes are ISO 8601 with timezone offset; naive datetimes are rejected
  with HTTP 400.
- Cursor pagination ordered by `-observed_at` (stable under append).
- Bucket aggregation accepts only the whitelist `1m, 5m, 15m, 1h, 1d`.
- Max query window without explicit `interval` is 7 days.

## Alternatives considered

**Header-based versioning** (`Accept: application/vnd.scm.v1+json`). Cleaner
from a REST purist's view but tooling-hostile: browsers can't pick a version
in the URL bar, curl invocations get longer, and caching reverse proxies need
to vary on the header. Rejected.

**Field-level versioning / deprecation flags.** Useful for very large APIs;
overkill here. We'd add it later if v1 grows to >50 endpoints.

**Mixing ingestion schemas and serializers** (pydantic models doubled as both).
Tempting because there's less code, but it means upstream changes leak into
the public API. The current separation has paid off twice already (epoch ms
timestamps in GBFS become ISO 8601 in our API).

## Consequences

- The OpenAPI schema is the canonical contract: drf-spectacular generates it
  from the code, and our frontend `openapi-typescript` codegen consumes it for
  type safety.
- We never need to ask "what version is the client sending?" — the URL says it.
- Adding endpoints is free; renaming or removing them needs a v2 conversation.
