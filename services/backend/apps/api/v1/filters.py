"""Shared filter helpers: since/until window parsing with timezone + max-window guard."""

from __future__ import annotations

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

MAX_WINDOW = timedelta(days=7)


def _parse_aware(value: str | None, field: str) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({field: f"must be ISO 8601, got {value!r}"}) from exc
    if parsed.tzinfo is None:
        raise ValidationError({field: "must include timezone offset (e.g. Z or +00:00)"})
    return parsed


def parse_window(
    query: dict[str, str], *, default_window: timedelta = timedelta(hours=24)
) -> tuple[datetime, datetime]:
    """Return (since, until) inclusive/exclusive half-open interval.

    `since` ISO 8601 with tz; defaults to (until - default_window).
    `until` ISO 8601 with tz; defaults to now (UTC).
    Window must be <= MAX_WINDOW (7 days).
    """
    until = _parse_aware(query.get("until"), "until") or timezone.now()
    since = _parse_aware(query.get("since"), "since") or (until - default_window)
    if since >= until:
        raise ValidationError({"since": "must be earlier than `until`"})
    if (until - since) > MAX_WINDOW:
        raise ValidationError(
            {"window": f"window must be <= {MAX_WINDOW.days} days; got {(until - since).days} days"}
        )
    return since, until
