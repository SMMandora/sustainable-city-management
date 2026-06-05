from __future__ import annotations

import httpx
from django.conf import settings

from apps.ingestion.exceptions import NonTransientError, TransientError

DUBLIN_LAT = "53.349805"
DUBLIN_LON = "-6.260310"


class OpenWeatherClient:
    """OpenWeather Current Weather API for Dublin."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = getattr(settings, "OPENWEATHER_API_KEY", "")

    def fetch_current_weather(self) -> httpx.Response:
        if not self.api_key:
            raise NonTransientError("OPENWEATHER_API_KEY not configured")
        params = {
            "lat": DUBLIN_LAT,
            "lon": DUBLIN_LON,
            "appid": self.api_key,
            "units": "metric",
        }
        url = f"{self.base_url}/weather"
        try:
            response = httpx.get(url, params=params, timeout=self.timeout)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            raise TransientError(f"weather: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise TransientError(f"weather: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise NonTransientError(f"weather: HTTP {response.status_code}")
        return response
