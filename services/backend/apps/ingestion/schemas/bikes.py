from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _epoch_seconds_to_dt(v: int | float | datetime) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromtimestamp(int(v), tz=UTC)


class GBFSStationInfo(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    station_id: Annotated[str, Field(min_length=1, max_length=64)]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    lat: Annotated[Decimal, Field(ge=Decimal("-90"), le=Decimal("90"))]
    lon: Annotated[Decimal, Field(ge=Decimal("-180"), le=Decimal("180"))]
    capacity: Annotated[int, Field(ge=0, le=1000)]


class GBFSStationStatus(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    station_id: Annotated[str, Field(min_length=1, max_length=64)]
    num_bikes_available: Annotated[int, Field(ge=0)]
    num_docks_available: Annotated[int, Field(ge=0)]
    is_installed: bool
    is_renting: bool
    is_returning: bool
    last_reported: datetime

    @field_validator("last_reported", mode="before")
    @classmethod
    def _last_reported_from_epoch(cls, v: object) -> datetime:
        if isinstance(v, int | float | datetime):
            return _epoch_seconds_to_dt(v)
        raise ValueError("last_reported must be epoch seconds")


class GBFSData(BaseModel):
    stations: list[dict[str, object]]


class GBFSStationInfoPayload(BaseModel):
    """Wrapper for station_information.json — the per-record schema is GBFSStationInfo."""

    model_config = ConfigDict(extra="ignore")

    last_updated: datetime
    ttl: Annotated[int, Field(ge=0)]
    version: str
    data: GBFSData

    @field_validator("last_updated", mode="before")
    @classmethod
    def _last_updated_from_epoch(cls, v: object) -> datetime:
        if isinstance(v, int | float | datetime):
            return _epoch_seconds_to_dt(v)
        raise ValueError("last_updated must be epoch seconds")


class GBFSStationStatusPayload(GBFSStationInfoPayload):
    """Same wrapper; per-record schema is GBFSStationStatus."""
