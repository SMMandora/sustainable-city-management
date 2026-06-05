from __future__ import annotations

from rest_framework.pagination import CursorPagination


class ObservedAtCursorPagination(CursorPagination):
    """Cursor pagination ordered by -observed_at. Default 100 per page; max 1000."""

    page_size = 100
    max_page_size = 1000
    page_size_query_param = "page_size"
    ordering = "-observed_at"
