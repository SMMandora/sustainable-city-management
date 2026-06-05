from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pybreaker
import pytest

from apps.ingestion.tasks import poll_source
from apps.observations.models import DataSource


@pytest.fixture
def enabled_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="dublin_bikes",
        display_name="Dublin Bikes",
        base_url="https://example/",
        enabled=True,
    )


def test_poll_source_skips_when_source_disabled(db: None) -> None:
    DataSource.objects.create(
        slug="dublin_bikes", display_name="X", base_url="https://example/", enabled=False
    )
    result = poll_source("dublin_bikes")
    assert result["skipped"] is True


def test_poll_source_skips_when_source_missing(db: None) -> None:
    result = poll_source("dublin_bikes")
    assert result["skipped"] is True


def test_poll_source_skips_when_slug_not_in_registry(db: None) -> None:
    DataSource.objects.create(
        slug="mystery", display_name="X", base_url="https://example/", enabled=True
    )
    result = poll_source("mystery")
    assert result["skipped"] is True
    assert result["reason"] == "no_registry_entry"


def test_poll_source_breaker_open_skips_feed(enabled_source: DataSource) -> None:
    """When the breaker is open, the task records skip and does not call pipeline."""
    with (
        patch("apps.ingestion.tasks.get_breaker") as mock_breaker_factory,
        patch("apps.ingestion.tasks.pipeline.process") as mock_process,
    ):
        breaker = MagicMock()
        breaker.call.side_effect = pybreaker.CircuitBreakerError("open")
        mock_breaker_factory.return_value = breaker
        result = poll_source("dublin_bikes")

    feeds = result["feeds"]
    assert len(feeds) == 2
    assert all(f["skipped"] is True and f["reason"] == "breaker_open" for f in feeds)
    mock_process.assert_not_called()


def test_poll_source_happy_path_invokes_pipeline_per_feed(enabled_source: DataSource) -> None:
    """Both feeds fetched, pipeline.process called once per feed."""
    fake_response = httpx.Response(
        200, content=b"{}", request=httpx.Request("GET", "https://example/x.json")
    )
    with (
        patch("apps.ingestion.tasks.get_breaker") as mock_breaker_factory,
        patch("apps.ingestion.tasks.pipeline.process") as mock_process,
    ):
        breaker = MagicMock()
        breaker.call.return_value = fake_response
        mock_breaker_factory.return_value = breaker
        mock_process.return_value = {
            "raw_id": 1,
            "validated": 0,
            "deadlettered": 0,
            "upserted": 0,
        }
        result = poll_source("dublin_bikes")

    assert mock_process.call_count == 2
    assert len(result["feeds"]) == 2
    assert all("skipped" not in f for f in result["feeds"])
