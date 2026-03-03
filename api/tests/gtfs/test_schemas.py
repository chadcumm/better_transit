import pytest
from pydantic import ValidationError

from better_transit.gtfs.schemas import (
    AgencyRow,
    CalendarDateRow,
    CalendarRow,
    RouteRow,
    ShapePointRow,
    StopRow,
    StopTimeRow,
    TripRow,
)


class TestAgencyRow:
    def test_valid(self):
        row = AgencyRow(
            agency_id="KCATA",
            agency_name="Kansas City Area Transportation Authority",
            agency_url="http://www.kcata.org",
            agency_timezone="America/Chicago",
        )
        assert row.agency_id == "KCATA"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            AgencyRow(agency_id="KCATA")


class TestStopRow:
    def test_valid(self):
        row = StopRow(
            stop_id="1161406",
            stop_name="ON N 110TH ST AT VILLAGE WEST APTS SB",
            stop_lat=39.127334,
            stop_lon=-94.835239,
        )
        assert row.stop_id == "1161406"
        assert row.stop_lat == pytest.approx(39.127334)

    def test_optional_fields_default_none(self):
        row = StopRow(
            stop_id="1",
            stop_name="Test Stop",
            stop_lat=39.0,
            stop_lon=-94.0,
        )
        assert row.stop_code is None
        assert row.location_type is None
        assert row.parent_station is None

    def test_empty_strings_become_none(self):
        row = StopRow(
            stop_id="1",
            stop_name="Test Stop",
            stop_lat=39.0,
            stop_lon=-94.0,
            stop_code="",
            parent_station="",
        )
        assert row.stop_code is None
        assert row.parent_station is None


class TestRouteRow:
    def test_valid(self):
        row = RouteRow(
            route_id="101",
            agency_id="KCATA",
            route_short_name="101",
            route_long_name="State",
            route_type=3,
        )
        assert row.route_id == "101"
        assert row.route_type == 3


class TestTripRow:
    def test_valid(self):
        row = TripRow(
            route_id="101",
            service_id="25.0.1",
            trip_id="285265",
            direction_id=0,
            shape_id="4819",
        )
        assert row.trip_id == "285265"


class TestStopTimeRow:
    def test_valid(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time="5:30:00",
            departure_time="5:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "5:30:00"

    def test_leading_space_stripped(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time=" 5:30:00",
            departure_time=" 5:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "5:30:00"

    def test_overnight_time(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time="25:30:00",
            departure_time="25:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "25:30:00"


class TestCalendarRow:
    def test_valid(self):
        row = CalendarRow(
            service_id="25.0.1",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date="20260215",
            end_date="20260404",
        )
        assert row.service_id == "25.0.1"
        assert row.monday is True
        assert row.saturday is False

    def test_int_booleans(self):
        row = CalendarRow(
            service_id="25.0.1",
            monday=1,
            tuesday=0,
            wednesday=1,
            thursday=0,
            friday=1,
            saturday=0,
            sunday=0,
            start_date="20260215",
            end_date="20260404",
        )
        assert row.monday is True
        assert row.tuesday is False


class TestCalendarDateRow:
    def test_valid(self):
        row = CalendarDateRow(
            service_id="25.39.1",
            date="20260217",
            exception_type=1,
        )
        assert row.exception_type == 1


class TestShapePointRow:
    def test_valid(self):
        row = ShapePointRow(
            shape_id="4819",
            shape_pt_lat=39.099234,
            shape_pt_lon=-94.573962,
            shape_pt_sequence=1,
            shape_dist_traveled=0.0,
        )
        assert row.shape_id == "4819"
