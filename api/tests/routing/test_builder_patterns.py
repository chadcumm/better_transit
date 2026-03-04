"""Tests for route pattern grouping in builder."""

from better_transit.routing.builder import _group_into_patterns
from better_transit.routing.data import StopTime, TripSchedule


def test_single_pattern():
    """All trips with same stops → one pattern."""
    trips = [
        TripSchedule(
            trip_id="T1",
            route_id="R1",
            stop_times=[
                StopTime("A", 100, 100),
                StopTime("B", 200, 200),
            ],
        ),
        TripSchedule(
            trip_id="T2",
            route_id="R1",
            stop_times=[
                StopTime("A", 300, 300),
                StopTime("B", 400, 400),
            ],
        ),
    ]

    patterns = _group_into_patterns("R1", trips)

    assert len(patterns) == 1
    pattern_id, stops, pattern_trips = patterns[0]
    assert pattern_id == "R1_p0"
    assert stops == ["A", "B"]
    assert len(pattern_trips) == 2


def test_two_patterns():
    """Trips with different stops → two patterns."""
    trips = [
        TripSchedule(
            trip_id="T1",
            route_id="R1",
            stop_times=[
                StopTime("A", 100, 100),
                StopTime("B", 200, 200),
                StopTime("C", 300, 300),
            ],
        ),
        TripSchedule(
            trip_id="TX",
            route_id="R1",
            stop_times=[
                StopTime("A", 100, 100),
                StopTime("C", 250, 250),
            ],
        ),
    ]

    patterns = _group_into_patterns("R1", trips)

    assert len(patterns) == 2
    # p0 should be the most common pattern (both have 1 trip, so
    # the longer one comes first as a tiebreaker)
    ids = [p[0] for p in patterns]
    assert "R1_p0" in ids
    assert "R1_p1" in ids


def test_most_common_pattern_is_p0():
    """The pattern with the most trips gets index 0."""
    trips = [
        TripSchedule(
            trip_id="T1",
            route_id="R1",
            stop_times=[StopTime("A", 100, 100), StopTime("B", 200, 200)],
        ),
        TripSchedule(
            trip_id="T2",
            route_id="R1",
            stop_times=[StopTime("A", 300, 300), StopTime("B", 400, 400)],
        ),
        TripSchedule(
            trip_id="TX",
            route_id="R1",
            stop_times=[StopTime("A", 100, 100), StopTime("C", 250, 250)],
        ),
    ]

    patterns = _group_into_patterns("R1", trips)

    assert len(patterns) == 2
    # p0 should be A->B (2 trips), p1 should be A->C (1 trip)
    p0 = next(p for p in patterns if p[0] == "R1_p0")
    assert p0[1] == ["A", "B"]
    assert len(p0[2]) == 2


def test_trips_sorted_by_departure():
    """Trips within a pattern should be sorted by first-stop departure."""
    trips = [
        TripSchedule(
            trip_id="T2",
            route_id="R1",
            stop_times=[StopTime("A", 300, 300), StopTime("B", 400, 400)],
        ),
        TripSchedule(
            trip_id="T1",
            route_id="R1",
            stop_times=[StopTime("A", 100, 100), StopTime("B", 200, 200)],
        ),
    ]

    patterns = _group_into_patterns("R1", trips)

    _, _, pattern_trips = patterns[0]
    assert pattern_trips[0].trip_id == "T1"
    assert pattern_trips[1].trip_id == "T2"
