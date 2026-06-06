from __future__ import annotations

import hashlib
from typing import Any

import httpx
import structlog
from pydantic import ValidationError

from apps.ingestion.registry import FeedConfig
from apps.observations.models import DataSource, DeadLetter, RawPayload

log = structlog.get_logger(__name__)


def process(source: DataSource, response: httpx.Response, feed: FeedConfig) -> dict[str, Any]:
    body_bytes = response.content
    try:
        body_json: Any = response.json()
    except ValueError as exc:
        raw = RawPayload.objects.create(
            source=source,
            request_url=str(response.url),
            response_status=response.status_code,
            body={"_unparseable": body_bytes.decode("utf-8", errors="replace")[:10_000]},
            sha256=hashlib.sha256(body_bytes).hexdigest(),
        )
        DeadLetter.objects.create(
            source=source,
            raw_payload=raw,
            stage=DeadLetter.Stage.PARSE,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )
        log.warning("ingest.unparseable", source=source.slug, feed=feed.name)
        return {"raw_id": raw.id, "validated": 0, "deadlettered": 1, "stage": "parse"}

    raw = RawPayload.objects.create(
        source=source,
        request_url=str(response.url),
        response_status=response.status_code,
        body=body_json,
        sha256=hashlib.sha256(body_bytes).hexdigest(),
    )

    try:
        feed.envelope_schema.model_validate(body_json)
    except ValidationError as exc:
        DeadLetter.objects.create(
            source=source,
            raw_payload=raw,
            stage=DeadLetter.Stage.PARSE,
            error_type="EnvelopeValidationError",
            error_message=str(exc),
            pydantic_errors=exc.errors(),
        )
        log.warning("ingest.envelope_invalid", source=source.slug, feed=feed.name)
        return {"raw_id": raw.id, "validated": 0, "deadlettered": 1, "stage": "envelope"}

    try:
        records: list[Any] = feed.records_extractor(body_json)
    except (KeyError, TypeError, AttributeError) as exc:
        DeadLetter.objects.create(
            source=source,
            raw_payload=raw,
            stage=DeadLetter.Stage.PARSE,
            error_type="RecordsExtractionError",
            error_message=str(exc),
        )
        return {"raw_id": raw.id, "validated": 0, "deadlettered": 1, "stage": "extract"}

    validated: list[Any] = []
    deadlettered = 0
    for record in records:
        try:
            validated.append(feed.record_schema.model_validate(record))
        except ValidationError as exc:
            DeadLetter.objects.create(
                source=source,
                raw_payload=raw,
                stage=DeadLetter.Stage.VALIDATION,
                error_type="ValidationError",
                error_message=str(exc),
                record=record,
                pydantic_errors=exc.errors(),
            )
            deadlettered += 1

    result = feed.persister(source, raw, validated)
    log.info(
        "ingest.processed",
        source=source.slug,
        feed=feed.name,
        validated=len(validated),
        deadlettered=deadlettered,
        **result,
    )
    if feed.sse_topic and result.get("upserted", 0) > 0:
        _publish(feed.sse_topic, source.slug, feed.name, result)
    return {
        "raw_id": raw.id,
        "validated": len(validated),
        "deadlettered": deadlettered,
        **result,
    }


def _publish(topic: str, source_slug: str, feed_name: str, summary: dict[str, int]) -> None:
    """Push an SSE delta to subscribers. Import locally so tests without
    Channels installed (or running) don't fail the pipeline import."""
    try:
        from django_eventstream import send_event
    except ImportError:
        return
    try:
        send_event(
            topic,
            "delta",
            {
                "source": source_slug,
                "feed": feed_name,
                "upserted": summary.get("upserted", 0),
            },
        )
    except Exception as exc:
        log.warning("sse.publish_failed", topic=topic, source=source_slug, error=str(exc))
