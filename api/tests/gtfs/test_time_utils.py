"""Tests for GTFS time conversion utilities."""

import datetime
from zoneinfo import ZoneInfo

from better_transit.gtfs.time_utils import gtfs_time_to_datetime, now_kansas_city

KC_TZ = ZoneInfo("America/Chicago")


def test_standard_time():
    """Normal daytime hours."""
    result = gtfs_time_to_datetime("14:30:00", datetime.date(2026, 3, 2))
    assert result == datetime.datetime(2026, 3, 2, 14, 30, 0, tzinfo=KC_TZ)
    assert result.isoformat() == "2026-03-02T14:30:00-06:00"


def test_midnight():
    result = gtfs_time_to_datetime("00:00:00", datetime.date(2026, 3, 2))
    assert result.hour == 0
    assert result.day == 2


def test_overnight_trip():
    """Hours >= 24 roll to the next day."""
    result = gtfs_time_to_datetime("25:30:00", datetime.date(2026, 3, 2))
    assert result.day == 3
    assert result.hour == 1
    assert result.minute == 30


def test_overnight_24_hours():
    """24:00:00 is midnight of the next day."""
    result = gtfs_time_to_datetime("24:00:00", datetime.date(2026, 3, 2))
    assert result.day == 3
    assert result.hour == 0


def test_dst_winter_cst():
    """In winter (CST), offset is -06:00."""
    result = gtfs_time_to_datetime("08:00:00", datetime.date(2026, 1, 15))
    assert result.utcoffset() == datetime.timedelta(hours=-6)


def test_dst_summer_cdt():
    """In summer (CDT), offset is -05:00."""
    result = gtfs_time_to_datetime("08:00:00", datetime.date(2026, 7, 15))
    assert result.utcoffset() == datetime.timedelta(hours=-5)


def test_dst_transition_spring():
    """Spring forward: March 8, 2026. Times after 2am switch to CDT."""
    result = gtfs_time_to_datetime("03:00:00", datetime.date(2026, 3, 8))
    assert result.utcoffset() == datetime.timedelta(hours=-5)


def test_zero_padded_time():
    result = gtfs_time_to_datetime("05:30:00", datetime.date(2026, 3, 2))
    assert result.hour == 5
    assert result.minute == 30


def test_now_kansas_city_has_timezone():
    now = now_kansas_city()
    assert now.tzinfo is not None
    assert str(now.tzinfo) == "America/Chicago"
