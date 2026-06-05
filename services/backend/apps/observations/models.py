from __future__ import annotations

from django.db import models


class DataSource(models.Model):
    slug = models.CharField(max_length=32, unique=True)
    display_name = models.CharField(max_length=128)
    base_url = models.URLField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.slug


class BikeStation(models.Model):
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="bike_stations")
    external_id = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    capacity = models.PositiveSmallIntegerField()
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="uniq_bike_station"),
        ]
        indexes = [models.Index(fields=["latitude", "longitude"])]

    def __str__(self) -> str:
        return f"{self.external_id} {self.name}"


class BikeAvailability(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN"
        CLOSED = "CLOSED"

    station = models.ForeignKey(BikeStation, on_delete=models.PROTECT, related_name="availability")
    observed_at = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    bikes_available = models.PositiveSmallIntegerField()
    stands_available = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=8, choices=Status.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["station", "observed_at"], name="uniq_bike_obs"),
        ]
        indexes = [
            models.Index(fields=["station", "-observed_at"], name="bikeavail_station_obs_idx"),
            models.Index(fields=["-observed_at"], name="bikeavail_obs_idx"),
        ]


class NoiseSensor(models.Model):
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="noise_sensors")
    external_id = models.CharField(max_length=64)
    label = models.CharField(max_length=200)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="uniq_noise_sensor"),
        ]
        indexes = [models.Index(fields=["latitude", "longitude"])]

    def __str__(self) -> str:
        return f"{self.external_id} {self.label}"


class NoiseReading(models.Model):
    sensor = models.ForeignKey(NoiseSensor, on_delete=models.PROTECT, related_name="readings")
    observed_at = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    laeq_db = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sensor", "observed_at"], name="uniq_noise_obs"),
        ]
        indexes = [
            models.Index(fields=["sensor", "-observed_at"], name="noise_sensor_obs_idx"),
            models.Index(fields=["-observed_at"], name="noise_obs_idx"),
        ]


class WeatherObservation(models.Model):
    source = models.ForeignKey(
        DataSource, on_delete=models.PROTECT, related_name="weather_observations"
    )
    observed_at = models.DateTimeField()
    ingested_at = models.DateTimeField(auto_now_add=True)
    temp_c = models.DecimalField(max_digits=4, decimal_places=1)
    humidity = models.PositiveSmallIntegerField()
    wind_speed_ms = models.DecimalField(max_digits=4, decimal_places=1)
    conditions = models.CharField(max_length=64)
    raw = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "observed_at"], name="uniq_weather_obs"),
        ]
        indexes = [models.Index(fields=["-observed_at"], name="weather_obs_idx")]


class RawPayload(models.Model):
    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="raw_payloads")
    fetched_at = models.DateTimeField(auto_now_add=True)
    request_url = models.URLField(max_length=500)
    response_status = models.PositiveSmallIntegerField()
    body = models.JSONField()
    sha256 = models.CharField(max_length=64, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["source", "-fetched_at"])]


class DeadLetter(models.Model):
    class Stage(models.TextChoices):
        PARSE = "parse"
        VALIDATION = "validation"
        PERSISTENCE = "persistence"
        TRANSPORT = "transport"

    source = models.ForeignKey(DataSource, on_delete=models.PROTECT, related_name="dead_letters")
    raw_payload = models.ForeignKey(
        RawPayload, on_delete=models.SET_NULL, null=True, blank=True, related_name="dead_letters"
    )
    failed_at = models.DateTimeField(auto_now_add=True)
    stage = models.CharField(max_length=16, choices=Stage.choices)
    error_type = models.CharField(max_length=128)
    error_message = models.TextField()
    record = models.JSONField(null=True, blank=True)
    pydantic_errors = models.JSONField(null=True, blank=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["source", "-failed_at"]),
            models.Index(fields=["resolved", "-failed_at"]),
        ]
