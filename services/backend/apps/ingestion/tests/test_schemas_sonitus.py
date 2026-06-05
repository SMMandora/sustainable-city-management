from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apps.ingestion.schemas.sonitus import (
    SonitusMonitor,
    SonitusMonitorsResponse,
    SonitusReading,
    SonitusReadingsResponse,
)


def test_monitor_valid() -> None:
    m = SonitusMonitor.model_validate(
        {"serial": "S1", "label": "St Stephen's Green", "latitude": "53.34", "longitude": "-6.26"}
    )
    assert m.serial == "S1"


@pytest.mark.parametrize(
    "field,value",
    [("serial", ""), ("label", ""), ("latitude", 91), ("longitude", 181)],
)
def test_monitor_rejects(field: str, value: object) -> None:
    payload = {"serial": "S1", "label": "X", "latitude": 53.34, "longitude": -6.26, field: value}
    with pytest.raises(ValidationError):
        SonitusMonitor.model_validate(payload)


def test_reading_valid() -> None:
    r = SonitusReading.model_validate(
        {"monitor_serial": "S1", "timestamp": "2026-06-01T12:00:00Z", "laeq": "62.5"}
    )
    assert r.laeq == pytest.approx(62.5)
    assert r.timestamp == datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize("laeq", [-1, 250])
def test_reading_rejects_laeq_out_of_range(laeq: float) -> None:
    with pytest.raises(ValidationError):
        SonitusReading.model_validate(
            {"monitor_serial": "S1", "timestamp": "2026-06-01T12:00:00Z", "laeq": laeq}
        )


def test_monitors_response_wraps_list() -> None:
    payload = {
        "monitors": [
            {"serial": "S1", "label": "A", "latitude": 53.34, "longitude": -6.26},
            {"serial": "S2", "label": "B", "latitude": 53.35, "longitude": -6.27},
        ]
    }
    env = SonitusMonitorsResponse.model_validate(payload)
    assert len(env.monitors) == 2


def test_readings_response_wraps_list() -> None:
    env = SonitusReadingsResponse.model_validate(
        {"readings": [{"monitor_serial": "S1", "timestamp": "2026-06-01T12:00:00Z", "laeq": 60}]}
    )
    assert env.readings[0].laeq == 60
