from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from apps.ingestion.schemas.bikes import (
    GBFSStationInfo,
    GBFSStationInfoPayload,
    GBFSStationStatus,
    GBFSStationStatusPayload,
)

# ---------- GBFSStationInfo ----------


def _info_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "station_id": "42",
        "name": "Smithfield North",
        "lat": "53.3505",
        "lon": "-6.2778",
        "capacity": 30,
    }
    base.update(overrides)
    return base


def test_station_info_valid() -> None:
    model = GBFSStationInfo.model_validate(_info_payload())
    assert model.station_id == "42"
    assert model.capacity == 30
    assert model.lat == Decimal("53.3505")


@pytest.mark.parametrize(
    "field,value",
    [
        ("station_id", ""),
        ("name", ""),
        ("lat", 91),
        ("lat", -91),
        ("lon", 181),
        ("lon", -181),
        ("capacity", -1),
        ("capacity", 5000),
    ],
)
def test_station_info_rejects_out_of_range(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        GBFSStationInfo.model_validate(_info_payload(**{field: value}))


def test_station_info_missing_required() -> None:
    payload = _info_payload()
    del payload["station_id"]
    with pytest.raises(ValidationError):
        GBFSStationInfo.model_validate(payload)


def test_station_info_ignores_unknown_fields() -> None:
    model = GBFSStationInfo.model_validate(_info_payload(address="extra", region_id="ignored"))
    assert model.station_id == "42"


# ---------- GBFSStationStatus ----------


def _status_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "station_id": "42",
        "num_bikes_available": 7,
        "num_docks_available": 23,
        "is_installed": True,
        "is_renting": True,
        "is_returning": True,
        "last_reported": 1_780_000_000,
    }
    base.update(overrides)
    return base


def test_station_status_valid() -> None:
    model = GBFSStationStatus.model_validate(_status_payload())
    assert model.station_id == "42"
    assert model.num_bikes_available == 7
    assert model.last_reported.tzinfo == UTC


def test_station_status_converts_epoch_to_aware_datetime() -> None:
    model = GBFSStationStatus.model_validate(_status_payload(last_reported=1_700_000_000))
    assert model.last_reported == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)


def test_station_status_accepts_datetime_passthrough() -> None:
    when = datetime(2026, 1, 1, tzinfo=UTC)
    model = GBFSStationStatus.model_validate(_status_payload(last_reported=when))
    assert model.last_reported == when


@pytest.mark.parametrize(
    "field,value",
    [
        ("num_bikes_available", -1),
        ("num_docks_available", -1),
        ("station_id", ""),
    ],
)
def test_station_status_rejects_invalid(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        GBFSStationStatus.model_validate(_status_payload(**{field: value}))


def test_station_status_rejects_string_last_reported() -> None:
    with pytest.raises(ValidationError):
        GBFSStationStatus.model_validate(_status_payload(last_reported="never"))


def test_station_status_rejects_missing_last_reported() -> None:
    payload = _status_payload()
    del payload["last_reported"]
    with pytest.raises(ValidationError):
        GBFSStationStatus.model_validate(payload)


# ---------- Envelope payloads ----------


def _envelope(stations: list[dict[str, object]]) -> dict[str, object]:
    return {
        "last_updated": 1_780_000_000,
        "ttl": 60,
        "version": "2.3",
        "data": {"stations": stations},
    }


def test_info_payload_envelope_valid() -> None:
    env = GBFSStationInfoPayload.model_validate(_envelope([_info_payload()]))
    assert env.ttl == 60
    assert env.last_updated.tzinfo == UTC


def test_status_payload_envelope_valid() -> None:
    env = GBFSStationStatusPayload.model_validate(_envelope([_status_payload()]))
    assert env.ttl == 60


def test_envelope_rejects_missing_data() -> None:
    payload = _envelope([])
    del payload["data"]
    with pytest.raises(ValidationError):
        GBFSStationInfoPayload.model_validate(payload)


def test_envelope_rejects_string_last_updated() -> None:
    with pytest.raises(ValidationError):
        GBFSStationInfoPayload.model_validate({**_envelope([]), "last_updated": "today"})


def test_envelope_rejects_negative_ttl() -> None:
    with pytest.raises(ValidationError):
        GBFSStationInfoPayload.model_validate({**_envelope([]), "ttl": -1})
