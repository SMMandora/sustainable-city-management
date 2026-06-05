from __future__ import annotations

import httpx
from django.conf import settings

from apps.ingestion.exceptions import NonTransientError, TransientError


class SonitusClient:
    """Sonitus noise/air-quality monitoring API.

    Requires SONITUS_USERNAME + SONITUS_PASSWORD in settings/env.
    Without credentials, every fetch raises NonTransientError and the
    source's DataSource row should stay disabled.
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.username = getattr(settings, "SONITUS_USERNAME", "")
        self.password = getattr(settings, "SONITUS_PASSWORD", "")

    def fetch_monitors(self) -> httpx.Response:
        return self._post("api/monitors", {})

    def fetch_recent_readings(self) -> httpx.Response:
        return self._post("api/recent_readings", {})

    def _post(self, path: str, body: dict[str, object]) -> httpx.Response:
        if not (self.username and self.password):
            raise NonTransientError("SONITUS_USERNAME/SONITUS_PASSWORD not configured")
        url = f"{self.base_url}/{path}"
        try:
            response = httpx.post(
                url,
                json={**body, "username": self.username, "password": self.password},
                timeout=self.timeout,
            )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            raise TransientError(f"{path}: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise TransientError(f"{path}: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise NonTransientError(f"{path}: HTTP {response.status_code}")
        return response
