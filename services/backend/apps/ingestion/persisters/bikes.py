from __future__ import annotations

from django.utils import timezone

from apps.ingestion.schemas.bikes import GBFSStationInfo, GBFSStationStatus
from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    DeadLetter,
    RawPayload,
)


def persist_bike_stations(
    source: DataSource,
    raw: RawPayload,
    validated: list[GBFSStationInfo],
) -> dict[str, int]:
    now = timezone.now()
    rows = [
        BikeStation(
            source=source,
            external_id=s.station_id,
            name=s.name,
            latitude=s.lat,
            longitude=s.lon,
            capacity=s.capacity,
            last_seen_at=now,
        )
        for s in validated
    ]
    BikeStation.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["source", "external_id"],
        update_fields=["name", "latitude", "longitude", "capacity", "last_seen_at"],
    )
    return {"upserted": len(rows)}


def persist_bike_availability(
    source: DataSource,
    raw: RawPayload,
    validated: list[GBFSStationStatus],
) -> dict[str, int]:
    existing = BikeStation.objects.filter(source=source).only("id", "external_id")
    stations_by_ext_id = {s.external_id: s for s in existing}
    rows: list[BikeAvailability] = []
    missing: list[GBFSStationStatus] = []
    for v in validated:
        station = stations_by_ext_id.get(v.station_id)
        if station is None:
            missing.append(v)
            continue
        is_open = v.is_installed and v.is_renting and v.is_returning
        rows.append(
            BikeAvailability(
                station=station,
                observed_at=v.last_reported,
                bikes_available=v.num_bikes_available,
                stands_available=v.num_docks_available,
                status=BikeAvailability.Status.OPEN if is_open else BikeAvailability.Status.CLOSED,
            )
        )
    if rows:
        BikeAvailability.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["station", "observed_at"],
            update_fields=["bikes_available", "stands_available", "status"],
        )
    for v in missing:
        DeadLetter.objects.create(
            source=source,
            raw_payload=raw,
            stage=DeadLetter.Stage.PERSISTENCE,
            error_type="MissingStation",
            error_message=f"Unknown station_id {v.station_id}",
            record=v.model_dump(mode="json"),
        )
    return {"upserted": len(rows), "missing_stations": len(missing)}
