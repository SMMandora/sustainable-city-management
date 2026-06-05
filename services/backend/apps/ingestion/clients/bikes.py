from __future__ import annotations

import httpx

from apps.ingestion.exceptions import NonTransientError, TransientError


class DublinBikesClient:
    """GBFS v2.x client for Dublin Bikes (api.cyclocity.fr/contracts/dublin/gbfs/v2/)."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch_station_information(self) -> httpx.Response:
        return self._get("station_information.json")

    def fetch_station_status(self) -> httpx.Response:
        return self._get("station_status.json")

    def _get(self, feed: str) -> httpx.Response:
        url = f"{self.base_url}/{feed}"
        try:
            response = httpx.get(url, timeout=self.timeout)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
            raise TransientError(f"{feed}: {exc.__class__.__name__}") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise TransientError(f"{feed}: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise NonTransientError(f"{feed}: HTTP {response.status_code}")
        return response
