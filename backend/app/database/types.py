"""Datetime type that keeps UTC values timezone-aware."""

from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def ensure_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class UtcDateTime(TypeDecorator[datetime]):
    """Store timezone-aware UTC datetimes on PostgreSQL and SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, _dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(
        self, value: datetime | None, _dialect: object
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
