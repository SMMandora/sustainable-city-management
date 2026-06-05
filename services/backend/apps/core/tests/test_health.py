from __future__ import annotations

from unittest.mock import patch

import pytest
from django.test import Client


def test_healthz_returns_ok(client: Client) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_ok_when_db_and_cache_ok(client: Client) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"


@pytest.mark.django_db
def test_readyz_503_when_database_fails(client: Client) -> None:
    with patch("apps.core.views.connection") as mock_conn:
        mock_conn.cursor.side_effect = RuntimeError("db down")
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"]["database"].startswith("error:")


@pytest.mark.django_db
def test_readyz_503_when_cache_fails(client: Client) -> None:
    with patch("apps.core.views.cache") as mock_cache:
        mock_cache.set.side_effect = RuntimeError("redis down")
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"]["cache"].startswith("error:")
