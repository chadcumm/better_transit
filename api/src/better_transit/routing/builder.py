"""Build RAPTOR data structures from database queries."""

import datetime
import time
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from better_transit.gtfs.models import Stop, StopTime, Trip
from better_transit.gtfs.queries import get_active_service_ids
from better_transit.routing.data import (
    RaptorData,
    Transfer,
    TransitRoute,
    TripSchedule,
    time_str_to_seconds,
)
from better_transit.routing.data import StopTime as RaptorStopTime

WALK_SPEED_MPS = 1.2  # Average walking speed: ~4.3 km/h

# Module-level cache: keyed by ISO date string, value is (timestamp, RaptorData)
_raptor_cache: dict[str, tuple[float, RaptorData]] = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _group_into_patterns(
    route_id: str,
    trips: list[TripSchedule],
) -> list[tuple[str, list[str], list[TripSchedule]]]:
    """Group trips by their stop pattern and assign pattern IDs.

    Returns a list of (pattern_id, ordered_stops, sorted_trips) tuples.
    The most common pattern gets index 0 (ties broken by longest pattern).
    Trips within each pattern are sorted by departure from first stop.
    """
    by_pattern: dict[tuple[str, ...], list[TripSchedule]] = defaultdict(list)
    for trip in trips:
        key = tuple(st.stop_id for st in trip.stop_times)
        by_pattern[key].append(trip)

    # Sort patterns: most trips first, then longest pattern as tiebreaker
    sorted_patterns = sorted(
        by_pattern.items(),
        key=lambda item: (-len(item[1]), -len(item[0])),
    )

    result = []
    for idx, (stop_tuple, pattern_trips) in enumerate(sorted_patterns):
        pattern_id = f"{route_id}_p{idx}"
        # Sort trips by departure from first stop
        pattern_trips.sort(key=lambda ts: ts.stop_times[0].departure)
        result.append((pattern_id, list(stop_tuple), pattern_trips))

    return result


async def get_raptor_data(
    session: AsyncSession,
    date: datetime.date,
) -> RaptorData:
    """Get RAPTOR data for a date, using a module-level cache with TTL.

    Cache key is the ISO date string. Rebuilds if:
    - No cached entry for this date
    - Cached entry is older than CACHE_TTL_SECONDS
    """
    key = date.isoformat()
    now = time.monotonic()

    if key in _raptor_cache:
        cached_time, cached_data = _raptor_cache[key]
        if now - cached_time < CACHE_TTL_SECONDS:
            return cached_data

    data = await build_raptor_data(session, date)
    _raptor_cache[key] = (now, data)

    # Evict stale entries for other dates
    stale_keys = [k for k, (t, _) in _raptor_cache.items() if now - t >= CACHE_TTL_SECONDS]
    for k in stale_keys:
        del _raptor_cache[k]

    return data


async def build_raptor_data(
    session: AsyncSession,
    date: datetime.date,
) -> RaptorData:
    """Build RAPTOR data structures for a given service date."""
    service_ids = await get_active_service_ids(session, date)
    if not service_ids:
        return RaptorData()

    # Get all trips for active services
    trips_stmt = (
        select(Trip)
        .where(Trip.service_id.in_(service_ids))
        .order_by(Trip.route_id, Trip.trip_id)
    )
    trips_result = await session.execute(trips_stmt)
    trips = list(trips_result.scalars().all())

    trip_ids = [t.trip_id for t in trips]
    if not trip_ids:
        return RaptorData()

    # Get all stop_times for these trips
    st_stmt = (
        select(StopTime)
        .where(StopTime.trip_id.in_(trip_ids))
        .order_by(StopTime.trip_id, StopTime.stop_sequence)
    )
    st_result = await session.execute(st_stmt)
    stop_times = list(st_result.scalars().all())

    # Group stop_times by trip
    trip_stop_times: dict[str, list[StopTime]] = defaultdict(list)
    for st in stop_times:
        trip_stop_times[st.trip_id].append(st)

    # Build route data
    routes_by_id: dict[str, TransitRoute] = {}
    stop_routes: dict[str, set[str]] = defaultdict(set)
    all_stop_ids: set[str] = set()

    # Group trips by route
    route_trips: dict[str, list[Trip]] = defaultdict(list)
    for trip in trips:
        route_trips[trip.route_id].append(trip)

    for route_id, route_trips_list in route_trips.items():
        # Build TripSchedule objects for each trip
        all_schedules = []
        for trip in route_trips_list:
            trip_sts = trip_stop_times.get(trip.trip_id, [])
            if not trip_sts:
                continue
            raptor_sts = [
                RaptorStopTime(
                    stop_id=st.stop_id,
                    arrival=time_str_to_seconds(st.arrival_time),
                    departure=time_str_to_seconds(st.departure_time),
                )
                for st in trip_sts
            ]
            all_schedules.append(TripSchedule(
                trip_id=trip.trip_id,
                route_id=route_id,
                stop_times=raptor_sts,
            ))

        if not all_schedules:
            continue

        # Group into patterns by stop sequence
        patterns = _group_into_patterns(route_id, all_schedules)

        for pattern_id, ordered_stops, pattern_trips in patterns:
            # Update route_id in each TripSchedule to the pattern ID
            for ts in pattern_trips:
                ts.route_id = pattern_id

            routes_by_id[pattern_id] = TransitRoute(
                route_id=pattern_id,
                stops=ordered_stops,
                trips=pattern_trips,
            )

            for stop_id in ordered_stops:
                stop_routes[stop_id].add(pattern_id)
                all_stop_ids.add(stop_id)

    # Build transfer graph (walking between nearby stops)
    transfers = await _build_transfers(session, all_stop_ids)

    return RaptorData(
        routes=routes_by_id,
        stop_routes={sid: sorted(rids) for sid, rids in stop_routes.items()},
        transfers=transfers,
        all_stop_ids=all_stop_ids,
    )


async def _build_transfers(
    session: AsyncSession,
    stop_ids: set[str],
    max_walk_meters: int = 400,
) -> dict[str, list[Transfer]]:
    """Build walking transfer edges between nearby stops.

    Uses a simplified approach: for each stop, find stops within
    max_walk_meters and compute walking time.
    """
    transfers: dict[str, list[Transfer]] = defaultdict(list)

    # Get all stop coordinates
    stops_stmt = select(Stop).where(Stop.stop_id.in_(stop_ids))
    stops_result = await session.execute(stops_stmt)
    stops = {s.stop_id: s for s in stops_result.scalars().all()}

    # Simple quadratic approach — fine for KCATA scale (~2000 stops)
    stop_list = list(stops.values())
    for i, s1 in enumerate(stop_list):
        for s2 in stop_list[i + 1 :]:
            dist = _haversine(s1.stop_lat, s1.stop_lon, s2.stop_lat, s2.stop_lon)
            if dist <= max_walk_meters:
                walk_time = int(dist / WALK_SPEED_MPS)
                transfers[s1.stop_id].append(
                    Transfer(s1.stop_id, s2.stop_id, walk_time)
                )
                transfers[s2.stop_id].append(
                    Transfer(s2.stop_id, s1.stop_id, walk_time)
                )

    return dict(transfers)


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in meters between two points using Haversine."""
    import math

    earth_radius = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
