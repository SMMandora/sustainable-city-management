"""Contract test for OpenWeather Dublin endpoint.

Replays a recorded cassette in CI; the cassette is committed. To re-record,
delete the cassette file and run with OPENWEATHER_API_KEY set.
"""

from __future__ import annotations

import pytest

from apps.ingestion.clients.weather import OpenWeatherClient
from apps.ingestion.schemas.weather import OpenWeatherCurrentPayload

from .conftest import source_vcr


@pytest.mark.contract
def test_openweather_dublin_matches_schema() -> None:
    with source_vcr.use_cassette(
        "openweather_dublin_current.yaml",
        filter_query_parameters=["appid"],
    ):
        response = OpenWeatherClient("https://api.openweathermap.org/data/2.5/").fetch_current_weather()

    payload = OpenWeatherCurrentPayload.model_validate(response.json())
    # name varies by neighborhood (Dublin/Mountjoy/etc.) — just assert non-empty
    assert payload.name
    assert -50 <= payload.main.temp <= 50
    assert 0 <= payload.main.humidity <= 100
    assert payload.weather[0].description
