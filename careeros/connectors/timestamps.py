from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def observation_timestamp(source_timestamp: object | None) -> str:
    if source_timestamp is not None:
        candidate = str(source_timestamp).strip()
        if candidate:
            return candidate
    return utc_now_iso()
