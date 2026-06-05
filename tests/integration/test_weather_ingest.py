"""End-to-end OpenWeather ingest via vcrpy cassette."""

from __future__ import annotations

import pytest

from apps.ingestion.tasks import poll_source
from apps.observations.models import DataSource, WeatherObservation

from tests.contract.conftest import source_vcr


@pytest.fixture
def openweather_source(db: None, settings: object) -> DataSource:
    settings.OPENWEATHER_API_KEY = "test-key"  # type: ignore[attr-defined]
    return DataSource.objects.create(
        slug="openweather",
        display_name="OpenWeather",
        base_url="https://api.openweathermap.org/data/2.5/",
        enabled=True,
    )


@pytest.mark.integration
def test_full_weather_poll_persists_observation(openweather_source: DataSource) -> None:
    with source_vcr.use_cassette(
        "openweather_dublin_current.yaml",
        filter_query_parameters=["appid"],
    ):
        result = poll_source("openweather")

    assert result["source"] == "openweather"
    assert WeatherObservation.objects.count() == 1
    obs = WeatherObservation.objects.get()
    assert obs.humidity > 0
    assert obs.conditions
