from __future__ import annotations


class IngestError(Exception):
    """Base for ingestion errors."""


class TransientError(IngestError):
    """Retryable: 5xx, 429, timeout, connection error."""


class NonTransientError(IngestError):
    """Non-retryable: 4xx (except 429), malformed response, schema mismatch."""
