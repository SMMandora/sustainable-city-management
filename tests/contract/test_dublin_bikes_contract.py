"""Contract tests: validate that the live upstream still matches our pydantic schemas.

These cassettes are committed; CI replays them, no live HTTP. To re-record,
delete the cassette file and run the test again.
"""

from __future__ import annotations

import pytest

from apps.ingestion.clients.bikes import DublinBikesClient
from apps.ingestion.schemas.bikes import (
    GBFSStationInfo,
    GBFSStationInfoPayload,
    GBFSStationStatus,
    GBFSStationStatusPayload,
)

from .conftest import source_vcr

BASE_URL = "https://api.cyclocity.fr/contracts/dublin/gbfs/v2"


@pytest.mark.contract
def test_dublin_bikes_station_information_matches_schema() -> None:
    with source_vcr.use_cassette("dublin_bikes_station_information.yaml"):
        response = DublinBikesClient(BASE_URL).fetch_station_information()

    payload = GBFSStationInfoPayload.model_validate(response.json())
    assert payload.version.startswith("2.")
    assert len(payload.data.stations) >= 50

    sample = payload.data.stations[0]
    parsed = GBFSStationInfo.model_validate(sample)
    assert parsed.station_id
    assert parsed.capacity > 0


@pytest.mark.contract
def test_dublin_bikes_station_status_matches_schema() -> None:
    with source_vcr.use_cassette("dublin_bikes_station_status.yaml"):
        response = DublinBikesClient(BASE_URL).fetch_station_status()

    payload = GBFSStationStatusPayload.model_validate(response.json())
    assert payload.version.startswith("2.")
    assert len(payload.data.stations) >= 50

    sample = payload.data.stations[0]
    parsed = GBFSStationStatus.model_validate(sample)
    assert parsed.station_id
    assert parsed.num_bikes_available >= 0
