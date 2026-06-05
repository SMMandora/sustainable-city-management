from __future__ import annotations

from apps.ingestion.schemas.weather import OpenWeatherCurrentPayload
from apps.observations.models import DataSource, RawPayload, WeatherObservation


def persist_weather(
    source: DataSource,
    raw: RawPayload,
    validated: list[OpenWeatherCurrentPayload],
) -> dict[str, int]:
    if not validated:
        return {"upserted": 0}
    rows = [
        WeatherObservation(
            source=source,
            observed_at=v.dt,
            temp_c=v.main.temp,
            humidity=v.main.humidity,
            wind_speed_ms=v.wind.speed,
            conditions=v.weather[0].description,
            raw=raw.body,
        )
        for v in validated
    ]
    WeatherObservation.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=["source", "observed_at"],
        update_fields=["temp_c", "humidity", "wind_speed_ms", "conditions", "raw"],
    )
    return {"upserted": len(rows)}
