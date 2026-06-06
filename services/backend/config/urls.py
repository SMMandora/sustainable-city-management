import django_eventstream
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("django_prometheus.urls")),
    path("api/v1/", include("apps.api.v1.urls")),
    path("api/v1/stream/bikes", include(django_eventstream.urls), {"channels": ["bikes"]}),
    path("api/v1/stream/noise", include(django_eventstream.urls), {"channels": ["noise"]}),
    path("api/v1/stream/weather", include(django_eventstream.urls), {"channels": ["weather"]}),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
