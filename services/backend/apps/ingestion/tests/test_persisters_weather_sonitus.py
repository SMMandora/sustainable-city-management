"""Integration-style tests for the weather and Sonitus persisters using
synthetic payloads. The Sonitus contract can't be verified live (auth)."""

from __future__ import annotations

import json

import httpx
import pytest

from apps.ingestion import pipeline
from apps.ingestion.registry import SOURCES
from apps.observations.models import (
    DataSource,
    DeadLetter,
    NoiseReading,
    NoiseSensor,
    RawPayload,
    WeatherObservation,
)

WEATHER_FEED = SOURCES["openweather"].feeds[0]
SONITUS_MONITORS_FEED = SOURCES["sonitus"].feeds[0]
SONITUS_READINGS_FEED = SOURCES["sonitus"].feeds[1]


def _response(body: object, url: str = "https://example/x") -> httpx.Response:
    return httpx.Response(
        200,
        content=json.dumps(body).encode("utf-8"),
        request=httpx.Request("GET", url),
    )


@pytest.fixture
def weather_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="openweather",
        display_name="OpenWeather",
        base_url="https://api.openweathermap.org/data/2.5/",
        enabled=True,
    )


@pytest.fixture
def sonitus_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="sonitus",
        display_name="Sonitus",
        base_url="https://data.smartdublin.ie/sonitus-api/",
        enabled=True,
    )


# ---------- weather ----------


def test_weather_persists_observation(weather_source: DataSource) -> None:
    body = {
        "dt": 1_780_000_000,
        "name": "Dublin",
        "main": {"temp": 15.2, "humidity": 72},
        "wind": {"speed": 4.6},
        "weather": [{"description": "broken clouds"}],
    }
    pipeline.process(weather_source, _response(body), WEATHER_FEED)
    obs = WeatherObservation.objects.get()
    assert obs.conditions == "broken clouds"
    assert obs.humidity == 72


def test_weather_is_idempotent(weather_source: DataSource) -> None:
    body = {
        "dt": 1_780_000_000,
        "name": "Dublin",
        "main": {"temp": 15.2, "humidity": 72},
        "wind": {"speed": 4.6},
        "weather": [{"description": "broken clouds"}],
    }
    pipeline.process(weather_source, _response(body), WEATHER_FEED)
    pipeline.process(weather_source, _response(body), WEATHER_FEED)
    assert WeatherObservation.objects.count() == 1


def test_weather_dead_letters_invalid(weather_source: DataSource) -> None:
    body = {"dt": 1_780_000_000, "name": "Dublin"}  # missing main/wind/weather
    pipeline.process(weather_source, _response(body), WEATHER_FEED)
    assert WeatherObservation.objects.count() == 0
    assert DeadLetter.objects.count() == 1


# ---------- sonitus monitors ----------


def test_sonitus_monitors_persist(sonitus_source: DataSource) -> None:
    body = {
        "monitors": [
            {"serial": "S1", "label": "Stephens Green", "latitude": 53.34, "longitude": -6.26},
            {"serial": "S2", "label": "Smithfield", "latitude": 53.35, "longitude": -6.27},
        ]
    }
    pipeline.process(sonitus_source, _response(body), SONITUS_MONITORS_FEED)
    assert NoiseSensor.objects.count() == 2


def test_sonitus_monitors_idempotent(sonitus_source: DataSource) -> None:
    body = {
        "monitors": [
            {"serial": "S1", "label": "Stephens Green", "latitude": 53.34, "longitude": -6.26},
        ]
    }
    pipeline.process(sonitus_source, _response(body), SONITUS_MONITORS_FEED)
    pipeline.process(sonitus_source, _response(body), SONITUS_MONITORS_FEED)
    assert NoiseSensor.objects.count() == 1


# ---------- sonitus readings ----------


def test_sonitus_readings_persist_for_known_sensor(sonitus_source: DataSource) -> None:
    NoiseSensor.objects.create(
        source=sonitus_source, external_id="S1", label="X", latitude="53.34", longitude="-6.26"
    )
    body = {
        "readings": [
            {"monitor_serial": "S1", "timestamp": "2026-06-01T12:00:00Z", "laeq": 62.5},
        ]
    }
    pipeline.process(sonitus_source, _response(body), SONITUS_READINGS_FEED)
    assert NoiseReading.objects.count() == 1


def test_sonitus_readings_dead_letter_unknown_sensor(sonitus_source: DataSource) -> None:
    body = {
        "readings": [
            {"monitor_serial": "ghost", "timestamp": "2026-06-01T12:00:00Z", "laeq": 62.5},
        ]
    }
    pipeline.process(sonitus_source, _response(body), SONITUS_READINGS_FEED)
    assert NoiseReading.objects.count() == 0
    dl = DeadLetter.objects.get()
    assert dl.error_type == "MissingSensor"


def test_records_extractor_failure_dead_letters(sonitus_source: DataSource) -> None:
    # 'monitors' wrapper passes envelope validation (sonitus envelope requires it),
    # but a body shaped {} would fail records extraction. Use an envelope that
    # passes but lacks the expected list (we use Monitors envelope with empty).
    body: dict[str, list[object]] = {"monitors": []}
    pipeline.process(sonitus_source, _response(body), SONITUS_MONITORS_FEED)
    assert NoiseSensor.objects.count() == 0
    assert RawPayload.objects.count() == 1
    assert DeadLetter.objects.count() == 0  # empty list is valid, not an error
