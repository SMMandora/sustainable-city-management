from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WeatherMain(BaseModel):
    model_config = ConfigDict(extra="ignore")
    temp: Decimal
    humidity: Annotated[int, Field(ge=0, le=100)]


class WeatherWind(BaseModel):
    model_config = ConfigDict(extra="ignore")
    speed: Annotated[Decimal, Field(ge=Decimal("0"))]


class WeatherCondition(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: Annotated[str, Field(min_length=1, max_length=64)]


class OpenWeatherCurrentPayload(BaseModel):
    """Schema for https://api.openweathermap.org/data/2.5/weather?units=metric"""

    model_config = ConfigDict(extra="ignore")

    dt: datetime
    name: Annotated[str, Field(min_length=1, max_length=64)]
    main: WeatherMain
    wind: WeatherWind
    weather: Annotated[list[WeatherCondition], Field(min_length=1)]

    @field_validator("dt", mode="before")
    @classmethod
    def _epoch_to_dt(cls, v: object) -> datetime:
        if isinstance(v, datetime):
            return v
        if isinstance(v, int | float):
            return datetime.fromtimestamp(int(v), tz=UTC)
        raise ValueError("dt must be epoch seconds")
