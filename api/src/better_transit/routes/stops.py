import asyncio
import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from better_transit.db import get_session
from better_transit.gtfs.queries import (
    get_active_service_ids,
    get_nearby_stops,
    get_routes_for_stops,
    get_stop_by_id,
    get_stop_times_for_stop,
    get_stop_times_for_stops,
)
from better_transit.gtfs.time_utils import gtfs_time_to_datetime, now_kansas_city
from better_transit.models.arrivals import ArrivalResponse
from better_transit.models.stops import NearbyStopResponse, StopResponse, StopRouteResponse
from better_transit.realtime.client import fetch_trip_updates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stops", tags=["stops"])


def _build_rt_index(trip_updates: list[dict]) -> dict[tuple[str, str], dict]:
    """Build a lookup index: (trip_id, stop_id) -> stop_time_update."""
    index: dict[tuple[str, str], dict] = {}
    for tu in trip_updates:
        trip_id = tu["trip_id"]
        for stu in tu.get("stop_time_updates", []):
            key = (trip_id, stu["stop_id"])
            index[key] = stu
    return index


def _make_arrival(
    d: dict,
    service_date: datetime.date,
    rt_index: dict[tuple[str, str], dict] | None = None,
    stop_id: str | None = None,
) -> ArrivalResponse:
    """Convert a stop_times query result dict to an ArrivalResponse.

    If rt_index is provided and contains a matching trip update,
    the arrival/departure times are adjusted by the delay.
    """
    scheduled_arrival = gtfs_time_to_datetime(d["arrival_time"], service_date)
    scheduled_departure = gtfs_time_to_datetime(d["departure_time"], service_date)

    arrival_dt = scheduled_arrival
    departure_dt = scheduled_departure
    delay = None
    is_realtime = False

    if rt_index and stop_id:
        key = (d["trip_id"], stop_id)
        rt_update = rt_index.get(key)
        if rt_update:
            is_realtime = True
            if rt_update.get("arrival_delay") is not None:
                delay = rt_update["arrival_delay"]
                arrival_dt = scheduled_arrival + datetime.timedelta(seconds=delay)
            if rt_update.get("departure_delay") is not None:
                departure_dt = scheduled_departure + datetime.timedelta(
                    seconds=rt_update["departure_delay"]
                )

    return ArrivalResponse(
        trip_id=d["trip_id"],
        route_id=d["route_id"],
        headsign=d["headsign"],
        arrival_time=arrival_dt.isoformat(),
        departure_time=departure_dt.isoformat(),
        scheduled_arrival_time=scheduled_arrival.isoformat(),
        scheduled_departure_time=scheduled_departure.isoformat(),
        delay_seconds=delay,
        is_realtime=is_realtime,
    )


@router.get("/nearby", response_model=list[NearbyStopResponse])
async def nearby_stops(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    radius: int = Query(800, ge=100, le=5000),
    limit: int = Query(20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Find stops near a location with routes and next arrivals."""
    stops = await get_nearby_stops(session, lat, lon, radius, limit)

    now = now_kansas_city()
    today = now.date()
    current_time = now.strftime("%H:%M:%S")
    service_ids = await get_active_service_ids(session, today)

    stop_ids = [s["stop_id"] for s in stops]

    # Batch queries: 2 queries instead of 2N
    trip_updates = await asyncio.to_thread(fetch_trip_updates)
    rt_index = _build_rt_index(trip_updates)

    routes_by_stop = await get_routes_for_stops(session, stop_ids)

    arrivals_by_stop: dict[str, list[dict]] = {}
    if service_ids:
        arrivals_by_stop = await get_stop_times_for_stops(
            session, stop_ids, service_ids, after_time=current_time
        )

    results = []
    for stop in stops:
        sid = stop["stop_id"]

        route_models = [
            StopRouteResponse(
                route_id=r["route_id"],
                route_short_name=r["route_short_name"],
                route_long_name=r["route_long_name"],
            )
            for r in routes_by_stop.get(sid, [])
        ]

        next_arrivals = [
            _make_arrival(d, today, rt_index, sid)
            for d in arrivals_by_stop.get(sid, [])
        ]

        results.append(
            NearbyStopResponse(
                stop_id=stop["stop_id"],
                stop_name=stop["stop_name"],
                stop_lat=stop["stop_lat"],
                stop_lon=stop["stop_lon"],
                distance_meters=stop["distance_meters"],
                routes=route_models,
                next_arrivals=next_arrivals,
            )
        )

    return results


@router.get("/{stop_id}", response_model=StopResponse)
async def stop_detail(
    stop_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get details for a single stop."""
    stop = await get_stop_by_id(session, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return StopResponse(
        stop_id=stop.stop_id,
        stop_name=stop.stop_name,
        stop_lat=stop.stop_lat,
        stop_lon=stop.stop_lon,
    )


@router.get("/{stop_id}/arrivals", response_model=list[ArrivalResponse])
async def stop_arrivals(
    stop_id: str,
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
):
    """Get upcoming arrivals at a stop with real-time predictions when available."""
    stop = await get_stop_by_id(session, stop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Stop not found")

    now = now_kansas_city()
    today = now.date()
    current_time = now.strftime("%H:%M:%S")

    service_ids = await get_active_service_ids(session, today)
    if not service_ids:
        return []

    departures = await get_stop_times_for_stop(
        session, stop_id, service_ids, after_time=current_time, limit=limit
    )

    trip_updates = await asyncio.to_thread(fetch_trip_updates)
    rt_index = _build_rt_index(trip_updates)

    return [_make_arrival(d, today, rt_index, stop_id) for d in departures]
