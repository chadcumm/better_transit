"""GTFS data access layer — all database queries for GTFS static data."""

import datetime

from geoalchemy2 import Geography
from sqlalchemy import and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from better_transit.gtfs.models import (
    Calendar,
    CalendarDate,
    Route,
    ShapeGeom,
    Stop,
    StopTime,
    Trip,
)

DAY_COLUMNS = {
    0: Calendar.monday,
    1: Calendar.tuesday,
    2: Calendar.wednesday,
    3: Calendar.thursday,
    4: Calendar.friday,
    5: Calendar.saturday,
    6: Calendar.sunday,
}


async def get_nearby_stops(
    session: AsyncSession,
    lat: float,
    lon: float,
    radius_meters: int = 800,
    limit: int = 20,
) -> list[dict]:
    """Find stops within radius_meters of (lat, lon), ordered by distance.

    Returns list of dicts with stop fields plus distance_meters.
    """
    point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    geography_point = cast(point, Geography)
    geography_geom = cast(Stop.geom, Geography)
    distance = func.ST_Distance(geography_geom, geography_point).label("distance_meters")

    stmt = (
        select(Stop, distance)
        .where(func.ST_DWithin(geography_geom, geography_point, radius_meters))
        .order_by(distance)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "stop_id": row.Stop.stop_id,
            "stop_name": row.Stop.stop_name,
            "stop_lat": row.Stop.stop_lat,
            "stop_lon": row.Stop.stop_lon,
            "distance_meters": round(row.distance_meters, 1),
        }
        for row in rows
    ]


async def get_stop_by_id(session: AsyncSession, stop_id: str) -> Stop | None:
    """Look up a single stop by ID."""
    stmt = select(Stop).where(Stop.stop_id == stop_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_routes(session: AsyncSession) -> list[Route]:
    """List all routes, ordered by short name."""
    stmt = select(Route).order_by(Route.route_short_name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_route_by_id(session: AsyncSession, route_id: str) -> Route | None:
    """Look up a single route by ID."""
    stmt = select(Route).where(Route.route_id == route_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_route_shape(session: AsyncSession, shape_id: str) -> ShapeGeom | None:
    """Get the shape geometry for a route."""
    stmt = select(ShapeGeom).where(ShapeGeom.shape_id == shape_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_stop_times_for_stop(
    session: AsyncSession,
    stop_id: str,
    service_ids: list[str],
    after_time: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Get upcoming departures at a stop for the given services.

    Returns list of dicts with stop_time fields plus route and trip info.
    """
    stmt = (
        select(StopTime, Trip.route_id, Trip.trip_headsign)
        .join(Trip, StopTime.trip_id == Trip.trip_id)
        .where(
            and_(
                StopTime.stop_id == stop_id,
                Trip.service_id.in_(service_ids),
            )
        )
    )
    if after_time:
        stmt = stmt.where(StopTime.departure_time >= after_time)

    stmt = stmt.order_by(StopTime.departure_time).limit(limit)
    result = await session.execute(stmt)
    rows = result.all()

    return [
        {
            "trip_id": row.StopTime.trip_id,
            "route_id": row.route_id,
            "headsign": row.trip_headsign,
            "arrival_time": row.StopTime.arrival_time,
            "departure_time": row.StopTime.departure_time,
            "stop_sequence": row.StopTime.stop_sequence,
        }
        for row in rows
    ]


async def get_routes_for_stop(
    session: AsyncSession,
    stop_id: str,
) -> list[dict]:
    """Get distinct routes serving a stop (via stop_times -> trips -> routes)."""
    stmt = (
        select(Route.route_id, Route.route_short_name, Route.route_long_name)
        .join(Trip, Route.route_id == Trip.route_id)
        .join(StopTime, Trip.trip_id == StopTime.trip_id)
        .where(StopTime.stop_id == stop_id)
        .distinct()
        .order_by(Route.route_short_name)
    )
    result = await session.execute(stmt)
    return [
        {
            "route_id": row.route_id,
            "route_short_name": row.route_short_name,
            "route_long_name": row.route_long_name,
        }
        for row in result.all()
    ]


async def get_routes_for_stops(
    session: AsyncSession,
    stop_ids: list[str],
) -> dict[str, list[dict]]:
    """Get distinct routes serving each stop in a batch query.

    Returns a dict keyed by stop_id, each value a list of route dicts.
    """
    if not stop_ids:
        return {}

    stmt = (
        select(
            StopTime.stop_id,
            Route.route_id,
            Route.route_short_name,
            Route.route_long_name,
        )
        .join(Trip, Route.route_id == Trip.route_id)
        .join(StopTime, Trip.trip_id == StopTime.trip_id)
        .where(StopTime.stop_id.in_(stop_ids))
        .distinct()
        .order_by(StopTime.stop_id, Route.route_short_name)
    )
    result = await session.execute(stmt)

    grouped: dict[str, list[dict]] = {sid: [] for sid in stop_ids}
    for row in result.all():
        grouped[row.stop_id].append({
            "route_id": row.route_id,
            "route_short_name": row.route_short_name,
            "route_long_name": row.route_long_name,
        })
    return grouped


async def get_stop_times_for_stops(
    session: AsyncSession,
    stop_ids: list[str],
    service_ids: list[str],
    after_time: str | None = None,
    limit_per_stop: int = 3,
) -> dict[str, list[dict]]:
    """Get upcoming departures at multiple stops in a batch query.

    Returns a dict keyed by stop_id, each value a list of departure dicts
    (up to limit_per_stop per stop).
    """
    if not stop_ids or not service_ids:
        return {}

    stmt = (
        select(StopTime, Trip.route_id, Trip.trip_headsign)
        .join(Trip, StopTime.trip_id == Trip.trip_id)
        .where(
            and_(
                StopTime.stop_id.in_(stop_ids),
                Trip.service_id.in_(service_ids),
            )
        )
    )
    if after_time:
        stmt = stmt.where(StopTime.departure_time >= after_time)

    stmt = stmt.order_by(StopTime.stop_id, StopTime.departure_time)
    result = await session.execute(stmt)

    grouped: dict[str, list[dict]] = {sid: [] for sid in stop_ids}
    for row in result.all():
        sid = row.StopTime.stop_id
        if len(grouped[sid]) >= limit_per_stop:
            continue
        grouped[sid].append({
            "trip_id": row.StopTime.trip_id,
            "route_id": row.route_id,
            "headsign": row.trip_headsign,
            "arrival_time": row.StopTime.arrival_time,
            "departure_time": row.StopTime.departure_time,
            "stop_sequence": row.StopTime.stop_sequence,
        })
    return grouped


async def get_shape_id_for_route(
    session: AsyncSession,
    route_id: str,
    service_ids: list[str] | None = None,
    direction_id: int | None = None,
) -> str | None:
    """Get the shape_id for a route from a representative trip.

    When service_ids and direction_id are provided, picks a trip matching
    those constraints for consistency with get_stops_for_route.
    """
    stmt = select(Trip.shape_id).where(
        and_(Trip.route_id == route_id, Trip.shape_id.is_not(None))
    )
    if service_ids:
        stmt = stmt.where(Trip.service_id.in_(service_ids))
    if direction_id is not None:
        stmt = stmt.where(Trip.direction_id == direction_id)
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_shape_as_geojson(
    session: AsyncSession,
    shape_id: str,
) -> str | None:
    """Get a shape geometry as GeoJSON string."""
    stmt = select(func.ST_AsGeoJSON(ShapeGeom.geom)).where(
        ShapeGeom.shape_id == shape_id
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_stops_for_route(
    session: AsyncSession,
    route_id: str,
    service_ids: list[str],
    direction_id: int | None = None,
) -> list[dict]:
    """Get ordered stops for a route (from a representative trip).

    Returns stops in stop_sequence order for one representative trip.
    """
    trip_stmt = (
        select(Trip.trip_id)
        .where(
            and_(
                Trip.route_id == route_id,
                Trip.service_id.in_(service_ids),
            )
        )
    )
    if direction_id is not None:
        trip_stmt = trip_stmt.where(Trip.direction_id == direction_id)
    trip_stmt = trip_stmt.limit(1)
    trip_result = await session.execute(trip_stmt)
    trip_id = trip_result.scalar_one_or_none()
    if not trip_id:
        return []

    stmt = (
        select(
            StopTime.stop_id,
            StopTime.stop_sequence,
            StopTime.arrival_time,
            StopTime.departure_time,
            Stop.stop_name,
            Stop.stop_lat,
            Stop.stop_lon,
        )
        .join(Stop, StopTime.stop_id == Stop.stop_id)
        .where(StopTime.trip_id == trip_id)
        .order_by(StopTime.stop_sequence)
    )
    result = await session.execute(stmt)
    return [
        {
            "stop_id": row.stop_id,
            "stop_name": row.stop_name,
            "stop_lat": row.stop_lat,
            "stop_lon": row.stop_lon,
            "stop_sequence": row.stop_sequence,
            "arrival_time": row.arrival_time,
            "departure_time": row.departure_time,
        }
        for row in result.all()
    ]


async def get_trips_for_route(
    session: AsyncSession,
    route_id: str,
    service_ids: list[str],
) -> list[Trip]:
    """Get all trips for a route on the given service days."""
    stmt = (
        select(Trip)
        .where(
            and_(
                Trip.route_id == route_id,
                Trip.service_id.in_(service_ids),
            )
        )
        .order_by(Trip.trip_id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# NOTE: Midnight–5 AM limitation
# GTFS allows departure times > 24:00:00 for overnight service (e.g., 25:30:00
# means 1:30 AM the next day). Between midnight and ~5 AM, we resolve today's
# service_ids, but overnight trips belong to yesterday's service. Those trips
# are invisible to the arrivals query during this window. To fix, we'd need to
# also resolve yesterday's services during early-morning hours. Accepted as a
# known limitation — KCATA has minimal overnight service.
async def get_active_service_ids(
    session: AsyncSession,
    date: datetime.date,
) -> list[str]:
    """Resolve which service_ids are active on a given date.

    Combines calendar (regular patterns) with calendar_dates (exceptions).
    """
    date_str = date.strftime("%Y%m%d")
    weekday = date.weekday()  # 0=Monday
    day_col = DAY_COLUMNS[weekday]

    # Regular services active on this weekday within date range
    cal_stmt = select(Calendar.service_id).where(
        and_(
            day_col == True,  # noqa: E712
            Calendar.start_date <= date_str,
            Calendar.end_date >= date_str,
        )
    )
    cal_result = await session.execute(cal_stmt)
    active = set(cal_result.scalars().all())

    # Calendar_dates exceptions: type 1 = added, type 2 = removed
    exc_stmt = select(CalendarDate.service_id, CalendarDate.exception_type).where(
        CalendarDate.date == date_str
    )
    exc_result = await session.execute(exc_stmt)
    for service_id, exc_type in exc_result.all():
        if exc_type == 1:
            active.add(service_id)
        elif exc_type == 2:
            active.discard(service_id)

    return sorted(active)
