"""RAPTOR data structures for round-based transit routing."""

from dataclasses import dataclass, field


@dataclass
class StopTime:
    """A stop visit within a trip."""

    stop_id: str
    arrival: int  # seconds since midnight
    departure: int  # seconds since midnight


@dataclass
class TripSchedule:
    """A trip's ordered stop times."""

    trip_id: str
    route_id: str
    stop_times: list[StopTime]


@dataclass
class TransitRoute:
    """A route with its ordered stops and trip schedules."""

    route_id: str
    stops: list[str]  # ordered stop_ids
    trips: list[TripSchedule]  # sorted by departure from first stop


@dataclass
class Transfer:
    """A walking transfer between two stops."""

    from_stop_id: str
    to_stop_id: str
    walk_seconds: int


@dataclass
class RaptorData:
    """Pre-built data structures for the RAPTOR algorithm."""

    routes: dict[str, TransitRoute] = field(default_factory=dict)
    stop_routes: dict[str, list[str]] = field(default_factory=dict)  # stop_id -> route_ids
    transfers: dict[str, list[Transfer]] = field(default_factory=dict)  # stop_id -> transfers
    all_stop_ids: set[str] = field(default_factory=set)


def time_str_to_seconds(t: str) -> int:
    """Convert HH:MM:SS to seconds since midnight. Handles hours >= 24."""
    parts = t.strip().split(":")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
