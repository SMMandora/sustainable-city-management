from __future__ import annotations

from django.utils import timezone

from apps.ingestion.schemas.sonitus import SonitusMonitor, SonitusReading
from apps.observations.models import (
    DataSource,
    DeadLetter,
    NoiseReading,
    NoiseSensor,
    RawPayload,
)


def persist_noise_sensors(
    source: DataSource,
    raw: RawPayload,
    validated: list[SonitusMonitor],
) -> dict[str, int]:
    now = timezone.now()
    rows = [
        NoiseSensor(
            source=source,
            external_id=m.serial,
            label=m.label,
            latitude=m.latitude,
            longitude=m.longitude,
            last_seen_at=now,
        )
        for m in validated
    ]
    if rows:
        NoiseSensor.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["source", "external_id"],
            update_fields=["label", "latitude", "longitude", "last_seen_at"],
        )
    return {"upserted": len(rows)}


def persist_noise_readings(
    source: DataSource,
    raw: RawPayload,
    validated: list[SonitusReading],
) -> dict[str, int]:
    sensors_by_serial = {
        s.external_id: s
        for s in NoiseSensor.objects.filter(source=source).only("id", "external_id")
    }
    rows: list[NoiseReading] = []
    missing: list[SonitusReading] = []
    for r in validated:
        sensor = sensors_by_serial.get(r.monitor_serial)
        if sensor is None:
            missing.append(r)
            continue
        rows.append(NoiseReading(sensor=sensor, observed_at=r.timestamp, laeq_db=r.laeq))
    if rows:
        NoiseReading.objects.bulk_create(
            rows,
            update_conflicts=True,
            unique_fields=["sensor", "observed_at"],
            update_fields=["laeq_db"],
        )
    for r in missing:
        DeadLetter.objects.create(
            source=source,
            raw_payload=raw,
            stage=DeadLetter.Stage.PERSISTENCE,
            error_type="MissingSensor",
            error_message=f"Unknown monitor_serial {r.monitor_serial}",
            record=r.model_dump(mode="json"),
        )
    return {"upserted": len(rows), "missing_sensors": len(missing)}
