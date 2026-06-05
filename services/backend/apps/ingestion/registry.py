from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from apps.ingestion.clients.bikes import DublinBikesClient
from apps.ingestion.clients.sonitus import SonitusClient
from apps.ingestion.clients.weather import OpenWeatherClient
from apps.ingestion.persisters.bikes import persist_bike_availability, persist_bike_stations
from apps.ingestion.persisters.sonitus import persist_noise_readings, persist_noise_sensors
from apps.ingestion.persisters.weather import persist_weather
from apps.ingestion.schemas.bikes import (
    GBFSStationInfo,
    GBFSStationInfoPayload,
    GBFSStationStatus,
    GBFSStationStatusPayload,
)
from apps.ingestion.schemas.sonitus import (
    SonitusMonitor,
    SonitusMonitorsResponse,
    SonitusReading,
    SonitusReadingsResponse,
)
from apps.ingestion.schemas.weather import OpenWeatherCurrentPayload


@dataclass(frozen=True)
class FeedConfig:
    name: str
    fetch_method: str
    envelope_schema: type[BaseModel]
    record_schema: type[BaseModel]
    records_extractor: Callable[[Any], list[Any]]
    persister: Callable[..., dict[str, int]]


@dataclass(frozen=True)
class SourceConfig:
    client_class: type[Any]
    feeds: list[FeedConfig]


def _gbfs_records(body: Any) -> list[Any]:
    result: list[Any] = body["data"]["stations"]
    return result


def _identity_records(body: Any) -> list[Any]:
    return [body]


SOURCES: dict[str, SourceConfig] = {
    "dublin_bikes": SourceConfig(
        client_class=DublinBikesClient,
        feeds=[
            FeedConfig(
                name="station_information",
                fetch_method="fetch_station_information",
                envelope_schema=GBFSStationInfoPayload,
                record_schema=GBFSStationInfo,
                records_extractor=_gbfs_records,
                persister=persist_bike_stations,
            ),
            FeedConfig(
                name="station_status",
                fetch_method="fetch_station_status",
                envelope_schema=GBFSStationStatusPayload,
                record_schema=GBFSStationStatus,
                records_extractor=_gbfs_records,
                persister=persist_bike_availability,
            ),
        ],
    ),
    "openweather": SourceConfig(
        client_class=OpenWeatherClient,
        feeds=[
            FeedConfig(
                name="current_weather",
                fetch_method="fetch_current_weather",
                envelope_schema=OpenWeatherCurrentPayload,
                record_schema=OpenWeatherCurrentPayload,
                records_extractor=_identity_records,
                persister=persist_weather,
            ),
        ],
    ),
    "sonitus": SourceConfig(
        client_class=SonitusClient,
        feeds=[
            FeedConfig(
                name="monitors",
                fetch_method="fetch_monitors",
                envelope_schema=SonitusMonitorsResponse,
                record_schema=SonitusMonitor,
                records_extractor=lambda body: body["monitors"],
                persister=persist_noise_sensors,
            ),
            FeedConfig(
                name="readings",
                fetch_method="fetch_recent_readings",
                envelope_schema=SonitusReadingsResponse,
                record_schema=SonitusReading,
                records_extractor=lambda body: body["readings"],
                persister=persist_noise_readings,
            ),
        ],
    ),
}
