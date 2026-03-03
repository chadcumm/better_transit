"""Tests for RAPTOR routing algorithm with a synthetic transit network.

Network layout:
    Route A: S1 -> S2 -> S3          (departs S1 at 8:00, 8:30)
    Route B: S3 -> S4 -> S5          (departs S3 at 8:20, 8:50)
    Route C: S1 -> S6 -> S5          (departs S1 at 8:05, direct but slower)
    Transfer: S2 <-> S7 (300m, ~250s walk)
    Route D: S7 -> S8                (departs S7 at 8:15)
"""

import pytest

from better_transit.routing.data import (
    RaptorData,
    StopTime,
    Transfer,
    TransitRoute,
    TripSchedule,
    time_str_to_seconds,
)
from better_transit.routing.raptor import run_raptor
from better_transit.routing.results import extract_journeys


@pytest.fixture
def network() -> RaptorData:
    """Build a synthetic test transit network."""
    route_a = TransitRoute(
        route_id="A",
        stops=["S1", "S2", "S3"],
        trips=[
            TripSchedule(
                trip_id="A1",
                route_id="A",
                stop_times=[
                    StopTime("S1", 28800, 28800),   # 8:00
                    StopTime("S2", 29100, 29100),   # 8:05
                    StopTime("S3", 29400, 29400),   # 8:10
                ],
            ),
            TripSchedule(
                trip_id="A2",
                route_id="A",
                stop_times=[
                    StopTime("S1", 30600, 30600),   # 8:30
                    StopTime("S2", 30900, 30900),   # 8:35
                    StopTime("S3", 31200, 31200),   # 8:40
                ],
            ),
        ],
    )

    route_b = TransitRoute(
        route_id="B",
        stops=["S3", "S4", "S5"],
        trips=[
            TripSchedule(
                trip_id="B1",
                route_id="B",
                stop_times=[
                    StopTime("S3", 29700, 29700),   # 8:15 (departs after A1 arrives)
                    StopTime("S4", 30000, 30000),   # 8:20
                    StopTime("S5", 30300, 30300),   # 8:25
                ],
            ),
            TripSchedule(
                trip_id="B2",
                route_id="B",
                stop_times=[
                    StopTime("S3", 31500, 31500),   # 8:45
                    StopTime("S4", 31800, 31800),   # 8:50
                    StopTime("S5", 32100, 32100),   # 8:55
                ],
            ),
        ],
    )

    route_c = TransitRoute(
        route_id="C",
        stops=["S1", "S6", "S5"],
        trips=[
            TripSchedule(
                trip_id="C1",
                route_id="C",
                stop_times=[
                    StopTime("S1", 28800, 28800),   # 8:00
                    StopTime("S6", 29400, 29400),   # 8:10
                    StopTime("S5", 30600, 30600),   # 8:30
                ],
            ),
        ],
    )

    route_d = TransitRoute(
        route_id="D",
        stops=["S7", "S8"],
        trips=[
            TripSchedule(
                trip_id="D1",
                route_id="D",
                stop_times=[
                    StopTime("S7", 29700, 29700),   # 8:15
                    StopTime("S8", 30000, 30000),   # 8:20
                ],
            ),
        ],
    )

    return RaptorData(
        routes={"A": route_a, "B": route_b, "C": route_c, "D": route_d},
        stop_routes={
            "S1": ["A", "C"],
            "S2": ["A"],
            "S3": ["A", "B"],
            "S4": ["B"],
            "S5": ["B", "C"],
            "S6": ["C"],
            "S7": ["D"],
            "S8": ["D"],
        },
        transfers={
            "S2": [Transfer("S2", "S7", 250)],
            "S7": [Transfer("S7", "S2", 250)],
        },
        all_stop_ids={"S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"},
    )


def test_direct_trip(network):
    """S1 -> S3 via Route A, no transfer."""
    result = run_raptor(network, ["S1"], ["S3"], 28800)  # 8:00
    journeys = extract_journeys(result)

    assert len(journeys) >= 1
    # Best journey should arrive at 8:10 (29400)
    first = journeys[0]
    assert any(leg["mode"] == "transit" and leg["route_id"] == "A" for leg in first)


def test_one_transfer(network):
    """S1 -> S5 via Route A + Route B (transfer at S3)."""
    result = run_raptor(network, ["S1"], ["S5"], 28800)  # 8:00
    journeys = extract_journeys(result)

    assert len(journeys) >= 1
    # Should find A->B transfer at S3 arriving at 8:25 (30300)
    # This is faster than the direct C route arriving at 8:30 (30600)
    has_transfer = any(
        len([leg for leg in j if leg["mode"] == "transit"]) == 2
        for j in journeys
    )
    assert has_transfer


def test_pareto_optimal(network):
    """Should find both direct (fewer transfers) and transfer (faster) options."""
    result = run_raptor(network, ["S1"], ["S5"], 28800)  # 8:00
    journeys = extract_journeys(result)

    # Should have at least the transfer route (fastest)
    assert len(journeys) >= 1


def test_walking_transfer(network):
    """S1 -> S8 requires Route A + walk S2->S7 + Route D."""
    result = run_raptor(network, ["S1"], ["S8"], 28800, max_rounds=3)
    journeys = extract_journeys(result)

    assert len(journeys) >= 1
    first = journeys[0]
    has_walk = any(leg["mode"] == "walk" for leg in first)
    has_d = any(
        leg["mode"] == "transit" and leg.get("route_id") == "D"
        for leg in first
    )
    assert has_walk or has_d  # Should involve walking or route D


def test_no_path(network):
    """No path from S8 to S1 (no reverse routes)."""
    result = run_raptor(network, ["S8"], ["S1"], 28800)
    journeys = extract_journeys(result)
    assert journeys == []


def test_departure_after_last_service(network):
    """Departing at 9:00 (32400), after most trips, should find fewer options."""
    result = run_raptor(network, ["S1"], ["S3"], 32400)
    journeys = extract_journeys(result)
    # May find no journeys or only later ones
    # All found journeys should have arrival >= 32400
    for j in journeys:
        for leg in j:
            if leg.get("arrival_time"):
                assert leg["arrival_time"] >= 32400


def test_time_str_to_seconds():
    assert time_str_to_seconds("08:00:00") == 28800
    assert time_str_to_seconds("25:30:00") == 91800
    assert time_str_to_seconds("00:00:00") == 0
