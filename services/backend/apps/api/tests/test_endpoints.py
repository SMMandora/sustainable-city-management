from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from django.test import Client

from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    NoiseReading,
    NoiseSensor,
    WeatherObservation,
)


@pytest.fixture
def bike_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="dublin_bikes", display_name="X", base_url="https://x/", enabled=True
    )


@pytest.fixture
def noise_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="sonitus", display_name="X", base_url="https://x/", enabled=False
    )


@pytest.fixture
def weather_source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="openweather", display_name="X", base_url="https://x/", enabled=True
    )


def _make_station(source: DataSource, ext_id: str = "42") -> BikeStation:
    return BikeStation.objects.create(
        source=source,
        external_id=ext_id,
        name="Smithfield",
        latitude="53.35",
        longitude="-6.27",
        capacity=30,
    )


def _make_availability(station: BikeStation, when: datetime, bikes: int = 5) -> BikeAvailability:
    return BikeAvailability.objects.create(
        station=station,
        observed_at=when,
        bikes_available=bikes,
        stands_available=30 - bikes,
        status=BikeAvailability.Status.OPEN,
    )


# ---------- sources ----------


def test_sources_list(client: Client, bike_source: DataSource) -> None:
    response = client.get("/api/v1/sources/")
    assert response.status_code == 200
    body = response.json()
    assert any(s["slug"] == "dublin_bikes" for s in body)


# ---------- bike stations ----------


def test_bike_stations_list(client: Client, bike_source: DataSource) -> None:
    _make_station(bike_source, "1")
    _make_station(bike_source, "2")
    response = client.get("/api/v1/bike-stations/")
    assert response.status_code == 200
    body = response.json()
    assert {s["external_id"] for s in body} == {"1", "2"}


def test_bike_station_detail(client: Client, bike_source: DataSource) -> None:
    _make_station(bike_source, "42")
    response = client.get("/api/v1/bike-stations/42/")
    assert response.status_code == 200
    assert response.json()["external_id"] == "42"


def test_bike_station_detail_404(client: Client, bike_source: DataSource) -> None:
    assert client.get("/api/v1/bike-stations/missing/").status_code == 404


# ---------- bike availability: pagination + since/until ----------


def test_bike_availability_since_inclusive_until_exclusive(
    client: Client, bike_source: DataSource
) -> None:
    station = _make_station(bike_source)
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    _make_availability(station, t0, bikes=1)
    _make_availability(station, t0 + timedelta(minutes=5), bikes=2)
    _make_availability(station, t0 + timedelta(minutes=10), bikes=3)

    # Window [t0+5min, t0+10min) — should include the middle row only
    since = (t0 + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    until = (t0 + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    response = client.get(f"/api/v1/bike-availability/?since={since}&until={until}")
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["bikes_available"] == 2


def test_bike_availability_filter_by_station(client: Client, bike_source: DataSource) -> None:
    a = _make_station(bike_source, "A")
    b = _make_station(bike_source, "B")
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    _make_availability(a, when)
    _make_availability(b, when)

    since = (when - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    response = client.get(f"/api/v1/bike-availability/?since={since}&station=A")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["station_external_id"] == "A"


def test_bike_availability_rejects_naive_datetime(client: Client) -> None:
    response = client.get("/api/v1/bike-availability/?since=2026-06-01T12:00:00")
    assert response.status_code == 400
    assert "since" in response.json()


def test_bike_availability_rejects_window_over_7_days(client: Client) -> None:
    since = "2026-06-01T00:00:00Z"
    until = "2026-06-10T00:00:00Z"
    response = client.get(f"/api/v1/bike-availability/?since={since}&until={until}")
    assert response.status_code == 400
    assert "window" in response.json()


def test_bike_availability_rejects_since_after_until(client: Client) -> None:
    response = client.get(
        "/api/v1/bike-availability/" "?since=2026-06-02T00:00:00Z&until=2026-06-01T00:00:00Z"
    )
    assert response.status_code == 400


def test_bike_availability_pagination(client: Client, bike_source: DataSource) -> None:
    station = _make_station(bike_source)
    base = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)
    for i in range(150):
        _make_availability(station, base + timedelta(minutes=i), bikes=i % 30)
    since = (base - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    until = (base + timedelta(hours=3)).isoformat().replace("+00:00", "Z")
    response = client.get(f"/api/v1/bike-availability/?since={since}&until={until}")
    body = response.json()
    assert len(body["results"]) == 100
    assert body["next"] is not None
    # Follow cursor
    next_response = client.get(body["next"])
    next_body = next_response.json()
    assert len(next_body["results"]) == 50


# ---------- buckets ----------


def test_bike_buckets_5m(client: Client, bike_source: DataSource) -> None:
    station = _make_station(bike_source)
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    for i in range(10):
        _make_availability(station, base + timedelta(minutes=i), bikes=i)

    since = (base - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    until = (base + timedelta(minutes=11)).isoformat().replace("+00:00", "Z")
    response = client.get(
        f"/api/v1/bike-availability/buckets/?station=42&interval=5m&since={since}&until={until}"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["station_external_id"] == "42"
    assert body["interval"] == "5m"
    # 10 minutes / 5 min = 2-3 buckets depending on alignment
    assert len(body["buckets"]) >= 2
    total_samples = sum(b["sample_count"] for b in body["buckets"])
    assert total_samples == 10


def test_bike_buckets_invalid_interval(client: Client, bike_source: DataSource) -> None:
    _make_station(bike_source)
    response = client.get("/api/v1/bike-availability/buckets/?station=42&interval=7m")
    assert response.status_code == 400


def test_bike_buckets_missing_station_param(client: Client) -> None:
    response = client.get("/api/v1/bike-availability/buckets/?interval=5m")
    assert response.status_code == 400


def test_bike_buckets_unknown_station_404(client: Client, bike_source: DataSource) -> None:
    response = client.get("/api/v1/bike-availability/buckets/?station=ghost&interval=5m")
    assert response.status_code == 404


# ---------- noise ----------


def test_noise_sensors_and_readings(client: Client, noise_source: DataSource) -> None:
    sensor = NoiseSensor.objects.create(
        source=noise_source, external_id="S1", label="A", latitude="53.34", longitude="-6.26"
    )
    base = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    for i in range(3):
        NoiseReading.objects.create(
            sensor=sensor, observed_at=base + timedelta(minutes=i), laeq_db=60
        )

    sensors_response = client.get("/api/v1/noise-sensors/")
    assert sensors_response.status_code == 200
    assert len(sensors_response.json()) == 1

    since = (base - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    until = (base + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    readings_response = client.get(f"/api/v1/noise-readings/?since={since}&until={until}")
    assert readings_response.status_code == 200
    assert len(readings_response.json()["results"]) == 3


# ---------- weather ----------


def test_weather_list(client: Client, weather_source: DataSource) -> None:
    when = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    WeatherObservation.objects.create(
        source=weather_source,
        observed_at=when,
        temp_c="15.2",
        humidity=72,
        wind_speed_ms="4.6",
        conditions="overcast clouds",
        raw={"name": "Dublin"},
    )
    since = (when - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    response = client.get(f"/api/v1/weather/?since={since}")
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["conditions"] == "overcast clouds"


# ---------- OpenAPI schema ----------


def test_openapi_schema_returns_valid_json(client: Client) -> None:
    response = client.get("/api/schema/?format=json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    paths = schema["paths"]
    assert "/api/v1/bike-availability/" in paths
    assert "/api/v1/bike-availability/buckets/" in paths
    assert "/api/v1/weather/" in paths
