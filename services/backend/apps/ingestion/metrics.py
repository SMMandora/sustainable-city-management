"""Custom Prometheus metrics for ingestion. Scraped via django-prometheus
at /metrics on the web service."""

from __future__ import annotations

import time
from typing import Final

import pybreaker
from prometheus_client import Counter, Gauge

records_total: Final[Counter] = Counter(
    "scm_ingest_records_total",
    "Records processed by ingestion pipeline.",
    labelnames=("source", "feed", "outcome"),
)

duration_seconds: Final[Gauge] = Gauge(
    "scm_ingest_duration_seconds",
    "Duration of the last ingest cycle, by feed.",
    labelnames=("source", "feed"),
)

circuit_breaker_state: Final[Gauge] = Gauge(
    "scm_circuit_breaker_state",
    "Circuit breaker state: 0=closed, 1=open, 2=half-open.",
    labelnames=("source",),
)

last_successful_poll_timestamp: Final[Gauge] = Gauge(
    "scm_last_successful_poll_timestamp",
    "Unix timestamp of the last successful poll, by source.",
    labelnames=("source",),
)

sse_clients: Final[Gauge] = Gauge(
    "scm_sse_clients",
    "Currently connected SSE clients, by topic.",
    labelnames=("topic",),
)


_BREAKER_STATE_INT = {
    pybreaker.STATE_CLOSED: 0,
    pybreaker.STATE_OPEN: 1,
    pybreaker.STATE_HALF_OPEN: 2,
}


def record_pipeline_result(
    source: str, feed: str, validated: int, deadlettered: int
) -> None:
    if validated:
        records_total.labels(source=source, feed=feed, outcome="ok").inc(validated)
    if deadlettered:
        records_total.labels(source=source, feed=feed, outcome="deadletter").inc(deadlettered)
    last_successful_poll_timestamp.labels(source=source).set(time.time())


def record_breaker_state(source: str, breaker: pybreaker.CircuitBreaker) -> None:
    state = _BREAKER_STATE_INT.get(breaker.current_state, 0)
    circuit_breaker_state.labels(source=source).set(state)
