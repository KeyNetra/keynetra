from __future__ import annotations

from datetime import UTC, datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat_z(value: datetime) -> str:
    return ensure_utc_datetime(value).isoformat().replace("+00:00", "Z")
