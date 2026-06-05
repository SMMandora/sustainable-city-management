from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, JsonResponse


def healthz(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def readyz(request: HttpRequest) -> JsonResponse:
    checks: dict[str, str] = {}
    status = 200

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc.__class__.__name__}"
        status = 503

    try:
        cache.set("readyz:probe", "1", timeout=5)
        if cache.get("readyz:probe") != "1":
            raise RuntimeError("cache roundtrip failed")
        checks["cache"] = "ok"
    except Exception as exc:
        checks["cache"] = f"error: {exc.__class__.__name__}"
        status = 503

    body = {"status": "ok" if status == 200 else "error", "checks": checks}
    return JsonResponse(body, status=status)
