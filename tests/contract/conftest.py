from __future__ import annotations

from pathlib import Path

import vcr

CASSETTE_DIR = Path(__file__).parent / "cassettes"

source_vcr = vcr.VCR(
    cassette_library_dir=str(CASSETTE_DIR),
    record_mode="once",
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["authorization", "cookie", "user-agent"],
    decode_compressed_response=True,
)
