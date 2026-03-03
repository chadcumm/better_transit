"""Utilities for converting GTFS time strings to timezone-aware datetimes."""

import datetime
from zoneinfo import ZoneInfo

KANSAS_CITY_TZ = ZoneInfo("America/Chicago")


def gtfs_time_to_datetime(
    time_str: str,
    service_date: datetime.date,
) -> datetime.datetime:
    """Convert a GTFS time string + service date to a timezone-aware datetime.

    GTFS times can exceed 24:00:00 for overnight trips (e.g., "25:30:00").
    In that case, the time rolls over to the next calendar day.

    Examples:
        "14:30:00", 2026-03-02 → 2026-03-02T14:30:00-06:00  (CST)
        "25:30:00", 2026-03-02 → 2026-03-03T01:30:00-06:00  (CST)
    """
    parts = time_str.strip().split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])

    # Handle overnight trips (hours >= 24)
    extra_days = hours // 24
    hours = hours % 24

    base_date = service_date + datetime.timedelta(days=extra_days)
    naive = datetime.datetime(
        base_date.year, base_date.month, base_date.day,
        hours, minutes, seconds,
    )
    return naive.replace(tzinfo=KANSAS_CITY_TZ)


def now_kansas_city() -> datetime.datetime:
    """Get the current time in America/Chicago timezone."""
    return datetime.datetime.now(tz=KANSAS_CITY_TZ)
