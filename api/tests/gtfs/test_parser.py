from pathlib import Path

import pytest

from better_transit.gtfs.parser import _parse_file, parse_gtfs_directory
from better_transit.gtfs.schemas import (
    AgencyRow,
    CalendarDateRow,
    CalendarRow,
    RouteRow,
    ShapePointRow,
    StopRow,
    StopTimeRow,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_gtfs_directory():
    result = parse_gtfs_directory(FIXTURES)
    assert "agency" in result
    assert "stops" in result
    assert "routes" in result
    assert "trips" in result
    assert "stop_times" in result
    assert "calendar" in result
    assert "calendar_dates" in result
    assert "shapes" in result


def test_parse_agency():
    result = parse_gtfs_directory(FIXTURES)
    agencies = result["agency"]
    assert len(agencies) == 1
    assert isinstance(agencies[0], AgencyRow)
    assert agencies[0].agency_id == "KCATA"


def test_parse_stops():
    result = parse_gtfs_directory(FIXTURES)
    stops = result["stops"]
    assert len(stops) == 2
    assert isinstance(stops[0], StopRow)
    assert stops[0].stop_id == "1161406"
    assert stops[0].stop_lat == pytest.approx(39.127334)


def test_parse_routes():
    result = parse_gtfs_directory(FIXTURES)
    routes = result["routes"]
    assert len(routes) == 2
    assert isinstance(routes[0], RouteRow)


def test_parse_stop_times_strips_leading_space():
    result = parse_gtfs_directory(FIXTURES)
    stop_times = result["stop_times"]
    assert len(stop_times) == 2
    assert isinstance(stop_times[0], StopTimeRow)
    assert stop_times[0].arrival_time == "05:30:00"  # leading space stripped + zero-padded


def test_parse_shapes():
    result = parse_gtfs_directory(FIXTURES)
    shapes = result["shapes"]
    assert len(shapes) == 4
    assert isinstance(shapes[0], ShapePointRow)


def test_parse_calendar():
    result = parse_gtfs_directory(FIXTURES)
    cal = result["calendar"]
    assert len(cal) == 1
    assert isinstance(cal[0], CalendarRow)
    assert cal[0].monday is True
    assert cal[0].saturday is False


def test_parse_calendar_dates():
    result = parse_gtfs_directory(FIXTURES)
    cal_dates = result["calendar_dates"]
    assert len(cal_dates) == 1
    assert isinstance(cal_dates[0], CalendarDateRow)


def test_error_threshold_aborts_on_high_error_rate(tmp_path: Path):
    """If >10% of rows fail validation, _parse_file should raise ValueError."""
    # Create a stops file where most rows are invalid (missing required stop_name)
    content = "stop_id,stop_name,stop_lat,stop_lon\n"
    # 1 valid row
    content += "1,Valid Stop,39.1,-94.5\n"
    # 9 invalid rows (missing stop_name)
    for i in range(2, 11):
        content += f"{i},,invalid_lat,invalid_lon\n"
    filepath = tmp_path / "stops.txt"
    filepath.write_text(content)

    with pytest.raises(ValueError, match="Too many validation errors"):
        _parse_file(filepath, StopRow)


def test_error_threshold_allows_low_error_rate(tmp_path: Path):
    """If <=10% of rows fail validation, _parse_file should succeed."""
    content = "stop_id,stop_name,stop_lat,stop_lon\n"
    # 9 valid rows
    for i in range(1, 10):
        content += f"{i},Stop {i},39.1,-94.5\n"
    # 1 invalid row (10% exactly, not exceeded)
    content += "10,,invalid_lat,invalid_lon\n"
    filepath = tmp_path / "stops.txt"
    filepath.write_text(content)

    result = _parse_file(filepath, StopRow)
    assert len(result) == 9
