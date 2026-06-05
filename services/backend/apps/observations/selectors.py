"""Read-side query helpers. The API depends on these; nothing here mutates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import connection

INTERVAL_MAP: dict[str, str] = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1h": "1 hour",
    "1d": "1 day",
}

ALLOWED_INTERVALS: tuple[str, ...] = tuple(INTERVAL_MAP)


def bike_availability_buckets(
    station_id: int,
    since: datetime,
    until: datetime,
    interval: str,
) -> list[dict[str, Any]]:
    pg_interval = INTERVAL_MAP[interval]
    sql = """
        SELECT
            date_bin(%s::interval, observed_at,
                     TIMESTAMP '2000-01-01' AT TIME ZONE 'UTC') AS bucket,
            AVG(bikes_available)::float AS avg_bikes,
            AVG(stands_available)::float AS avg_stands,
            COUNT(*) AS sample_count
        FROM observations_bikeavailability
        WHERE station_id = %s AND observed_at >= %s AND observed_at < %s
        GROUP BY bucket
        ORDER BY bucket
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [pg_interval, station_id, since, until])
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]


def noise_reading_buckets(
    sensor_id: int,
    since: datetime,
    until: datetime,
    interval: str,
) -> list[dict[str, Any]]:
    pg_interval = INTERVAL_MAP[interval]
    sql = """
        SELECT
            date_bin(%s::interval, observed_at,
                     TIMESTAMP '2000-01-01' AT TIME ZONE 'UTC') AS bucket,
            AVG(laeq_db)::float AS avg_laeq_db,
            MAX(laeq_db)::float AS max_laeq_db,
            COUNT(*) AS sample_count
        FROM observations_noisereading
        WHERE sensor_id = %s AND observed_at >= %s AND observed_at < %s
        GROUP BY bucket
        ORDER BY bucket
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [pg_interval, sensor_id, since, until])
        cols = [c[0] for c in cursor.description]
        return [dict(zip(cols, row, strict=True)) for row in cursor.fetchall()]
