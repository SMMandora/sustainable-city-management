"""End-to-end ingestion test: drives poll_source against vcrpy cassettes,
asserts rows land in the DB."""

from __future__ import annotations

import pytest

from apps.ingestion.tasks import poll_source
from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    DeadLetter,
    RawPayload,
)

from tests.contract.conftest import source_vcr


@pytest.fixture
def dublin_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="dublin_bikes",
        display_name="Dublin Bikes",
        base_url="https://api.cyclocity.fr/contracts/dublin/gbfs/v2/",
        enabled=True,
    )


@pytest.mark.integration
def test_full_poll_creates_stations_and_availability(dublin_source: DataSource) -> None:
    with source_vcr.use_cassette("dublin_bikes_full_poll.yaml"):
        result = poll_source("dublin_bikes")

    assert result["source"] == "dublin_bikes"
    assert len(result["feeds"]) == 2

    assert BikeStation.objects.count() >= 50
    assert BikeAvailability.objects.count() >= 50
    assert RawPayload.objects.count() == 2
    # Upstream occasionally returns a station in status but not in information,
    # or with invalid info — we dead-letter and keep going. Cap so a regression
    # that loses all stations would still trip the test.
    assert DeadLetter.objects.count() < 10


@pytest.mark.integration
def test_full_poll_is_idempotent(dublin_source: DataSource) -> None:
    with source_vcr.use_cassette("dublin_bikes_full_poll.yaml"):
        poll_source("dublin_bikes")

    station_count_after_first = BikeStation.objects.count()
    availability_count_after_first = BikeAvailability.objects.count()

    with source_vcr.use_cassette("dublin_bikes_full_poll.yaml"):
        poll_source("dublin_bikes")

    assert BikeStation.objects.count() == station_count_after_first
    assert BikeAvailability.objects.count() == availability_count_after_first
    assert RawPayload.objects.count() == 4
