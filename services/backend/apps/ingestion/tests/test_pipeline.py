from __future__ import annotations

import json

import httpx
import pytest

from apps.ingestion import pipeline
from apps.ingestion.registry import SOURCES
from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    DeadLetter,
    RawPayload,
)

INFO_FEED = SOURCES["dublin_bikes"].feeds[0]
STATUS_FEED = SOURCES["dublin_bikes"].feeds[1]


def _response(
    body: object, *, status: int = 200, url: str = "https://example/station_status.json"
) -> httpx.Response:
    content = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
    return httpx.Response(
        status_code=status,
        content=content,
        request=httpx.Request("GET", url),
    )


def _info_envelope(stations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "last_updated": 1_780_000_000,
        "ttl": 300,
        "version": "2.3",
        "data": {"stations": stations},
    }


def _status_envelope(stations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "last_updated": 1_780_000_000,
        "ttl": 1,
        "version": "2.3",
        "data": {"stations": stations},
    }


def _make_station(source: DataSource, ext_id: str = "42") -> BikeStation:
    return BikeStation.objects.create(
        source=source,
        external_id=ext_id,
        name="X",
        latitude="53.35",
        longitude="-6.27",
        capacity=30,
    )


@pytest.fixture
def source(db: None) -> DataSource:
    return DataSource.objects.create(
        slug="dublin_bikes",
        display_name="Dublin Bikes",
        base_url="https://example/",
        enabled=True,
    )


# ---------- envelope-level failures ----------


def test_unparseable_body_creates_raw_and_dead_letter(source: DataSource) -> None:
    resp = _response(b"not-json-at-all", url="https://example/x.json")
    result = pipeline.process(source, resp, INFO_FEED)

    assert result["validated"] == 0
    assert result["deadlettered"] == 1
    assert RawPayload.objects.count() == 1
    raw = RawPayload.objects.get()
    assert "_unparseable" in raw.body
    dl = DeadLetter.objects.get()
    assert dl.stage == DeadLetter.Stage.PARSE


def test_envelope_validation_error_creates_raw_and_dead_letter(source: DataSource) -> None:
    bad = {"version": "2.3"}  # missing data, last_updated, ttl
    resp = _response(bad)
    result = pipeline.process(source, resp, STATUS_FEED)

    assert result["validated"] == 0
    assert result["deadlettered"] == 1
    assert RawPayload.objects.count() == 1
    dl = DeadLetter.objects.get()
    assert dl.stage == DeadLetter.Stage.PARSE
    assert dl.error_type == "EnvelopeValidationError"
    assert dl.pydantic_errors is not None


# ---------- record-level: good and bad in same batch ----------


def test_partial_failure_persists_good_dead_letters_bad(source: DataSource) -> None:
    good = {
        "station_id": "42",
        "name": "Good",
        "lat": 53.35,
        "lon": -6.27,
        "capacity": 30,
    }
    bad = {
        "station_id": "43",
        "name": "Bad",
        "lat": 53.35,
        "lon": -6.27,
        "capacity": -1,  # invalid
    }
    resp = _response(_info_envelope([good, bad]))
    result = pipeline.process(source, resp, INFO_FEED)

    assert result["validated"] == 1
    assert result["deadlettered"] == 1
    assert BikeStation.objects.count() == 1
    dl = DeadLetter.objects.get()
    assert dl.stage == DeadLetter.Stage.VALIDATION
    assert dl.record == bad
    assert dl.pydantic_errors is not None


# ---------- idempotency ----------


def test_running_twice_does_not_duplicate_stations(source: DataSource) -> None:
    env = _info_envelope(
        [
            {
                "station_id": "42",
                "name": "X",
                "lat": 53.35,
                "lon": -6.27,
                "capacity": 30,
            }
        ]
    )
    pipeline.process(source, _response(env), INFO_FEED)
    pipeline.process(source, _response(env), INFO_FEED)
    assert BikeStation.objects.count() == 1
    assert RawPayload.objects.count() == 2


def test_running_twice_does_not_duplicate_availability(source: DataSource) -> None:
    _make_station(source)
    env = _status_envelope(
        [
            {
                "station_id": "42",
                "num_bikes_available": 5,
                "num_docks_available": 25,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            }
        ]
    )
    pipeline.process(source, _response(env), STATUS_FEED)
    pipeline.process(source, _response(env), STATUS_FEED)
    assert BikeAvailability.objects.count() == 1


# ---------- unknown station_id is dead-lettered, not lost ----------


def test_unknown_station_id_in_status_is_dead_lettered(source: DataSource) -> None:
    env = _status_envelope(
        [
            {
                "station_id": "ghost",
                "num_bikes_available": 1,
                "num_docks_available": 1,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            }
        ]
    )
    pipeline.process(source, _response(env), STATUS_FEED)

    assert BikeAvailability.objects.count() == 0
    dl = DeadLetter.objects.get()
    assert dl.stage == DeadLetter.Stage.PERSISTENCE
    assert dl.error_type == "MissingStation"
    assert dl.record is not None
    assert dl.record["station_id"] == "ghost"


def test_status_persists_known_skips_unknown(source: DataSource) -> None:
    _make_station(source, "42")
    env = _status_envelope(
        [
            {
                "station_id": "42",
                "num_bikes_available": 5,
                "num_docks_available": 25,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            },
            {
                "station_id": "ghost",
                "num_bikes_available": 1,
                "num_docks_available": 1,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            },
        ]
    )
    pipeline.process(source, _response(env), STATUS_FEED)
    assert BikeAvailability.objects.count() == 1
    assert DeadLetter.objects.filter(error_type="MissingStation").count() == 1


# ---------- status mapping ----------


def test_status_open_when_all_flags_true(source: DataSource) -> None:
    _make_station(source)
    env = _status_envelope(
        [
            {
                "station_id": "42",
                "num_bikes_available": 0,
                "num_docks_available": 30,
                "is_installed": True,
                "is_renting": True,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            }
        ]
    )
    pipeline.process(source, _response(env), STATUS_FEED)
    assert BikeAvailability.objects.get().status == BikeAvailability.Status.OPEN


def test_status_closed_when_any_flag_false(source: DataSource) -> None:
    _make_station(source)
    env = _status_envelope(
        [
            {
                "station_id": "42",
                "num_bikes_available": 0,
                "num_docks_available": 30,
                "is_installed": True,
                "is_renting": False,
                "is_returning": True,
                "last_reported": 1_780_000_000,
            }
        ]
    )
    pipeline.process(source, _response(env), STATUS_FEED)
    assert BikeAvailability.objects.get().status == BikeAvailability.Status.CLOSED
