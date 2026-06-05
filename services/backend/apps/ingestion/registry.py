from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from apps.ingestion.clients.bikes import DublinBikesClient
from apps.ingestion.persisters.bikes import persist_bike_availability, persist_bike_stations
from apps.ingestion.schemas.bikes import (
    GBFSStationInfo,
    GBFSStationInfoPayload,
    GBFSStationStatus,
    GBFSStationStatusPayload,
)


@dataclass(frozen=True)
class FeedConfig:
    name: str
    fetch_method: str
    envelope_schema: type[BaseModel]
    record_schema: type[BaseModel]
    persister: Callable[..., dict[str, int]]


@dataclass(frozen=True)
class SourceConfig:
    client_class: type[Any]
    feeds: list[FeedConfig]


SOURCES: dict[str, SourceConfig] = {
    "dublin_bikes": SourceConfig(
        client_class=DublinBikesClient,
        feeds=[
            FeedConfig(
                name="station_information",
                fetch_method="fetch_station_information",
                envelope_schema=GBFSStationInfoPayload,
                record_schema=GBFSStationInfo,
                persister=persist_bike_stations,
            ),
            FeedConfig(
                name="station_status",
                fetch_method="fetch_station_status",
                envelope_schema=GBFSStationStatusPayload,
                record_schema=GBFSStationStatus,
                persister=persist_bike_availability,
            ),
        ],
    ),
}
