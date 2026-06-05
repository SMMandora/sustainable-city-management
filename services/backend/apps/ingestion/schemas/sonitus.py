"""Sonitus noise sensor schemas.

These are best-effort based on the Sonitus Systems dashboard / public docs;
they may need adjustment when real credentials are supplied and a contract
cassette is recorded.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SonitusMonitor(BaseModel):
    """Monitor dimension (one per physical sensor)."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    serial: Annotated[str, Field(min_length=1, max_length=64)]
    label: Annotated[str, Field(min_length=1, max_length=200)]
    latitude: Annotated[Decimal, Field(ge=Decimal("-90"), le=Decimal("90"))]
    longitude: Annotated[Decimal, Field(ge=Decimal("-180"), le=Decimal("180"))]


class SonitusReading(BaseModel):
    """A single LAeq reading from a monitor."""

    model_config = ConfigDict(extra="ignore")

    monitor_serial: Annotated[str, Field(min_length=1, max_length=64)]
    timestamp: datetime
    laeq: Annotated[Decimal, Field(ge=Decimal("0"), le=Decimal("200"))]


class SonitusMonitorsResponse(BaseModel):
    """List of monitors. Wrapper exists so we can validate at the envelope level."""

    model_config = ConfigDict(extra="ignore")
    monitors: list[SonitusMonitor]


class SonitusReadingsResponse(BaseModel):
    """List of readings."""

    model_config = ConfigDict(extra="ignore")
    readings: list[SonitusReading]
