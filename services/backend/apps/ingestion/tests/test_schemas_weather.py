from __future__ import annotations

from datetime import UTC

import pytest
from pydantic import ValidationError

from apps.ingestion.schemas.weather import OpenWeatherCurrentPayload


def _payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "dt": 1_780_000_000,
        "name": "Dublin",
        "main": {"temp": "15.2", "humidity": 72},
        "wind": {"speed": "4.6"},
        "weather": [{"description": "broken clouds"}],
    }
    base.update(overrides)
    return base


def test_payload_valid() -> None:
    model = OpenWeatherCurrentPayload.model_validate(_payload())
    assert model.name == "Dublin"
    assert model.main.humidity == 72
    assert model.dt.tzinfo == UTC


def test_payload_rejects_missing_main() -> None:
    p = _payload()
    del p["main"]
    with pytest.raises(ValidationError):
        OpenWeatherCurrentPayload.model_validate(p)


def test_payload_rejects_empty_weather_list() -> None:
    with pytest.raises(ValidationError):
        OpenWeatherCurrentPayload.model_validate(_payload(weather=[]))


@pytest.mark.parametrize("humidity", [-1, 101])
def test_payload_rejects_humidity_out_of_range(humidity: int) -> None:
    with pytest.raises(ValidationError):
        OpenWeatherCurrentPayload.model_validate(_payload(main={"temp": 1, "humidity": humidity}))


def test_payload_rejects_negative_wind_speed() -> None:
    with pytest.raises(ValidationError):
        OpenWeatherCurrentPayload.model_validate(_payload(wind={"speed": -1}))


def test_payload_rejects_string_dt() -> None:
    with pytest.raises(ValidationError):
        OpenWeatherCurrentPayload.model_validate(_payload(dt="yesterday"))


def test_payload_ignores_extra_fields() -> None:
    model = OpenWeatherCurrentPayload.model_validate(_payload(visibility=10000, cod=200))
    assert model.name == "Dublin"
