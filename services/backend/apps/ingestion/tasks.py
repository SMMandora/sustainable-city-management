from __future__ import annotations

from typing import Any

import pybreaker
import structlog
from celery import shared_task

from apps.ingestion import pipeline
from apps.ingestion.circuit import get_breaker
from apps.ingestion.exceptions import TransientError
from apps.ingestion.registry import SOURCES
from apps.observations.models import DataSource

log = structlog.get_logger(__name__)


@shared_task(  # type: ignore[untyped-decorator]
    bind=True,
    autoretry_for=(TransientError,),
    retry_backoff=2,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def poll_source(self: Any, source_slug: str) -> dict[str, Any]:
    source = DataSource.objects.filter(slug=source_slug, enabled=True).first()
    if source is None:
        log.info("ingest.skip_disabled", source=source_slug)
        return {"source": source_slug, "skipped": True}

    if source_slug not in SOURCES:
        log.error("ingest.no_registry_entry", source=source_slug)
        return {"source": source_slug, "skipped": True, "reason": "no_registry_entry"}

    config = SOURCES[source_slug]
    breaker = get_breaker(source_slug)
    client = config.client_class(source.base_url)

    summaries: list[dict[str, Any]] = []
    for feed in config.feeds:
        fetch = getattr(client, feed.fetch_method)
        try:
            response = breaker.call(fetch)
        except pybreaker.CircuitBreakerError:
            log.warning("ingest.breaker_open", source=source_slug, feed=feed.name)
            summaries.append({"feed": feed.name, "skipped": True, "reason": "breaker_open"})
            continue
        summary = pipeline.process(source, response, feed)
        summary["feed"] = feed.name
        summaries.append(summary)

    return {"source": source_slug, "feeds": summaries}
