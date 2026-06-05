from __future__ import annotations

from rest_framework import serializers

from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    NoiseReading,
    NoiseSensor,
    WeatherObservation,
)


class DataSourceSerializer(serializers.ModelSerializer[DataSource]):
    class Meta:
        model = DataSource
        fields = ("slug", "display_name", "base_url", "enabled")


class BikeStationSerializer(serializers.ModelSerializer[BikeStation]):
    class Meta:
        model = BikeStation
        fields = (
            "external_id",
            "name",
            "latitude",
            "longitude",
            "capacity",
            "first_seen_at",
            "last_seen_at",
        )


class BikeAvailabilitySerializer(serializers.ModelSerializer[BikeAvailability]):
    station_external_id = serializers.CharField(source="station.external_id", read_only=True)
    station_name = serializers.CharField(source="station.name", read_only=True)

    class Meta:
        model = BikeAvailability
        fields = (
            "station_external_id",
            "station_name",
            "observed_at",
            "bikes_available",
            "stands_available",
            "status",
        )


class NoiseSensorSerializer(serializers.ModelSerializer[NoiseSensor]):
    class Meta:
        model = NoiseSensor
        fields = (
            "external_id",
            "label",
            "latitude",
            "longitude",
            "first_seen_at",
            "last_seen_at",
        )


class NoiseReadingSerializer(serializers.ModelSerializer[NoiseReading]):
    sensor_external_id = serializers.CharField(source="sensor.external_id", read_only=True)
    sensor_label = serializers.CharField(source="sensor.label", read_only=True)

    class Meta:
        model = NoiseReading
        fields = ("sensor_external_id", "sensor_label", "observed_at", "laeq_db")


class WeatherObservationSerializer(serializers.ModelSerializer[WeatherObservation]):
    class Meta:
        model = WeatherObservation
        fields = (
            "observed_at",
            "temp_c",
            "humidity",
            "wind_speed_ms",
            "conditions",
        )


class BucketSerializer(serializers.Serializer[dict[str, object]]):
    bucket = serializers.DateTimeField()
    sample_count = serializers.IntegerField()


class BikeBucketSerializer(BucketSerializer):
    avg_bikes = serializers.FloatField()
    avg_stands = serializers.FloatField()


class NoiseBucketSerializer(BucketSerializer):
    avg_laeq_db = serializers.FloatField()
    max_laeq_db = serializers.FloatField()
