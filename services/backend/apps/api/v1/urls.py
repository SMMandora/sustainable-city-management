from __future__ import annotations

from django.urls import path

from . import views

app_name = "api_v1"

urlpatterns = [
    path("sources/", views.DataSourceList.as_view(), name="sources"),
    path("bike-stations/", views.BikeStationList.as_view(), name="bike-stations"),
    path(
        "bike-stations/<str:external_id>/",
        views.BikeStationDetail.as_view(),
        name="bike-station-detail",
    ),
    path("bike-availability/", views.BikeAvailabilityList.as_view(), name="bike-availability"),
    path(
        "bike-availability/buckets/",
        views.BikeAvailabilityBuckets.as_view(),
        name="bike-availability-buckets",
    ),
    path("noise-sensors/", views.NoiseSensorList.as_view(), name="noise-sensors"),
    path("noise-readings/", views.NoiseReadingList.as_view(), name="noise-readings"),
    path(
        "noise-readings/buckets/",
        views.NoiseReadingBuckets.as_view(),
        name="noise-readings-buckets",
    ),
    path("weather/", views.WeatherList.as_view(), name="weather"),
]
