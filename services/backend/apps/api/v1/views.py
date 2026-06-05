from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.observations import selectors
from apps.observations.models import (
    BikeAvailability,
    BikeStation,
    DataSource,
    NoiseReading,
    NoiseSensor,
    WeatherObservation,
)

from . import serializers as ser
from .filters import parse_window
from .pagination import ObservedAtCursorPagination

SINCE_PARAM = OpenApiParameter(
    name="since",
    type=str,
    location=OpenApiParameter.QUERY,
    description="ISO 8601 with timezone offset. Inclusive lower bound on observed_at.",
)
UNTIL_PARAM = OpenApiParameter(
    name="until",
    type=str,
    location=OpenApiParameter.QUERY,
    description="ISO 8601 with timezone offset. Exclusive upper bound on observed_at.",
)
INTERVAL_PARAM = OpenApiParameter(
    name="interval",
    type=str,
    location=OpenApiParameter.QUERY,
    description="Bucket size: one of 1m, 5m, 15m, 1h, 1d.",
    required=True,
)


class DataSourceList(generics.ListAPIView[DataSource]):
    queryset = DataSource.objects.all().order_by("slug")
    serializer_class = ser.DataSourceSerializer
    pagination_class = None


class BikeStationList(generics.ListAPIView[BikeStation]):
    queryset = BikeStation.objects.select_related("source").order_by("external_id")
    serializer_class = ser.BikeStationSerializer
    pagination_class = None


class BikeStationDetail(generics.RetrieveAPIView[BikeStation]):
    serializer_class = ser.BikeStationSerializer
    lookup_field = "external_id"
    lookup_url_kwarg = "external_id"
    queryset = BikeStation.objects.select_related("source")


class BikeAvailabilityList(generics.ListAPIView[BikeAvailability]):
    serializer_class = ser.BikeAvailabilitySerializer
    pagination_class = ObservedAtCursorPagination

    @extend_schema(parameters=[SINCE_PARAM, UNTIL_PARAM, OpenApiParameter("station", str)])
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> Any:
        since, until = parse_window(self.request.query_params)
        qs = (
            BikeAvailability.objects.select_related("station")
            .filter(observed_at__gte=since, observed_at__lt=until)
            .order_by("-observed_at")
        )
        station_id = self.request.query_params.get("station")
        if station_id:
            qs = qs.filter(station__external_id=station_id)
        return qs


class BikeAvailabilityBuckets(APIView):
    @extend_schema(
        parameters=[
            SINCE_PARAM,
            UNTIL_PARAM,
            INTERVAL_PARAM,
            OpenApiParameter("station", str, required=True),
        ],
        responses=ser.BikeBucketSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        station_ext_id = request.query_params.get("station")
        if not station_ext_id:
            raise ValidationError({"station": "required"})
        station = get_object_or_404(BikeStation, external_id=station_ext_id)

        interval = request.query_params.get("interval", "5m")
        if interval not in selectors.ALLOWED_INTERVALS:
            raise ValidationError(
                {"interval": f"must be one of {sorted(selectors.ALLOWED_INTERVALS)}"}
            )

        since, until = parse_window(request.query_params)
        buckets = selectors.bike_availability_buckets(station.id, since, until, interval)
        data = ser.BikeBucketSerializer(instance=buckets, many=True).data  # type: ignore[arg-type]
        return Response(
            {
                "station_external_id": station.external_id,
                "interval": interval,
                "since": since,
                "until": until,
                "buckets": data,
            }
        )


class NoiseSensorList(generics.ListAPIView[NoiseSensor]):
    queryset = NoiseSensor.objects.select_related("source").order_by("external_id")
    serializer_class = ser.NoiseSensorSerializer
    pagination_class = None


class NoiseReadingList(generics.ListAPIView[NoiseReading]):
    serializer_class = ser.NoiseReadingSerializer
    pagination_class = ObservedAtCursorPagination

    @extend_schema(parameters=[SINCE_PARAM, UNTIL_PARAM, OpenApiParameter("sensor", str)])
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> Any:
        since, until = parse_window(self.request.query_params)
        qs = (
            NoiseReading.objects.select_related("sensor")
            .filter(observed_at__gte=since, observed_at__lt=until)
            .order_by("-observed_at")
        )
        sensor_id = self.request.query_params.get("sensor")
        if sensor_id:
            qs = qs.filter(sensor__external_id=sensor_id)
        return qs


class NoiseReadingBuckets(APIView):
    @extend_schema(
        parameters=[
            SINCE_PARAM,
            UNTIL_PARAM,
            INTERVAL_PARAM,
            OpenApiParameter("sensor", str, required=True),
        ],
        responses=ser.NoiseBucketSerializer(many=True),
    )
    def get(self, request: Request) -> Response:
        sensor_ext_id = request.query_params.get("sensor")
        if not sensor_ext_id:
            raise ValidationError({"sensor": "required"})
        sensor = get_object_or_404(NoiseSensor, external_id=sensor_ext_id)

        interval = request.query_params.get("interval", "5m")
        if interval not in selectors.ALLOWED_INTERVALS:
            raise ValidationError(
                {"interval": f"must be one of {sorted(selectors.ALLOWED_INTERVALS)}"}
            )

        since, until = parse_window(request.query_params)
        buckets = selectors.noise_reading_buckets(sensor.id, since, until, interval)
        data = ser.NoiseBucketSerializer(instance=buckets, many=True).data  # type: ignore[arg-type]
        return Response(
            {
                "sensor_external_id": sensor.external_id,
                "interval": interval,
                "since": since,
                "until": until,
                "buckets": data,
            }
        )


class WeatherList(generics.ListAPIView[WeatherObservation]):
    serializer_class = ser.WeatherObservationSerializer
    pagination_class = ObservedAtCursorPagination

    @extend_schema(parameters=[SINCE_PARAM, UNTIL_PARAM])
    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> Any:
        since, until = parse_window(self.request.query_params)
        return WeatherObservation.objects.filter(
            observed_at__gte=since, observed_at__lt=until
        ).order_by("-observed_at")
