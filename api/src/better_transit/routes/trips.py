import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from better_transit.db import get_session
from better_transit.gtfs.queries import get_nearby_stops
from better_transit.gtfs.time_utils import KANSAS_CITY_TZ, now_kansas_city
from better_transit.models.trips import TripLeg, TripPlanRequest, TripPlanResponse
from better_transit.routing.builder import build_raptor_data
from better_transit.routing.raptor import run_raptor
from better_transit.routing.results import extract_journeys

router = APIRouter(prefix="/trips", tags=["trips"])

WALK_RADIUS_M = 800


@router.post("/plan", response_model=list[TripPlanResponse])
async def plan_trip(
    request: TripPlanRequest,
    session: AsyncSession = Depends(get_session),
):
    """Plan a trip between two locations using RAPTOR algorithm."""
    now = now_kansas_city()
    today = now.date()

    # Determine departure time
    if request.departure_time:
        dep_dt = datetime.datetime.fromisoformat(request.departure_time)
        if dep_dt.tzinfo is None:
            dep_dt = dep_dt.replace(tzinfo=KANSAS_CITY_TZ)
        dep_seconds = dep_dt.hour * 3600 + dep_dt.minute * 60 + dep_dt.second
    else:
        dep_seconds = now.hour * 3600 + now.minute * 60 + now.second

    # Find nearby stops for origin and destination
    origin_stops = await get_nearby_stops(
        session, request.origin_lat, request.origin_lon, WALK_RADIUS_M, limit=10
    )
    dest_stops = await get_nearby_stops(
        session, request.destination_lat, request.destination_lon, WALK_RADIUS_M, limit=10
    )

    if not origin_stops or not dest_stops:
        return []

    source_ids = [s["stop_id"] for s in origin_stops]
    target_ids = [s["stop_id"] for s in dest_stops]

    # Build RAPTOR data and run algorithm
    raptor_data = await build_raptor_data(session, today)
    if not raptor_data.routes:
        return []

    max_rounds = min(request.max_transfers + 1, 5)

    result = run_raptor(
        raptor_data,
        source_ids,
        target_ids,
        dep_seconds,
        max_rounds=max_rounds,
    )

    journeys = extract_journeys(result)

    # Convert to response format
    responses = []
    for journey in journeys:
        legs = []
        walking_seconds = 0
        transit_count = 0
        last_arrival = dep_seconds

        for leg in journey:
            if leg["mode"] == "walk":
                duration = leg.get("arrival_time", 0) - dep_seconds
                walk_time = max(duration, 0)
                walking_seconds += walk_time
                legs.append(TripLeg(
                    mode="walk",
                    from_stop_id=leg.get("from_stop_id"),
                    to_stop_id=leg.get("to_stop_id"),
                ))
            elif leg["mode"] == "transit":
                transit_count += 1
                board_time = leg.get("departure_time") or leg.get("arrival_time", 0)
                alight_time = leg.get("arrival_time", 0)
                legs.append(TripLeg(
                    mode="transit",
                    from_stop_id=leg.get("from_stop_id"),
                    to_stop_id=leg.get("to_stop_id"),
                    route_id=leg.get("route_id"),
                    departure_time=_seconds_to_iso(board_time, today),
                    arrival_time=_seconds_to_iso(alight_time, today),
                ))
                last_arrival = max(last_arrival, leg.get("arrival_time", 0))

        total_duration = last_arrival - dep_seconds
        transfer_count = max(transit_count - 1, 0)

        responses.append(TripPlanResponse(
            legs=legs,
            total_duration_seconds=max(total_duration, 0),
            walking_seconds=walking_seconds,
            transfer_count=transfer_count,
        ))

    return responses


def _seconds_to_iso(seconds: int, date: datetime.date) -> str:
    """Convert seconds since midnight to ISO 8601 string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    # Handle overnight
    extra_days = hours // 24
    hours = hours % 24
    d = date + datetime.timedelta(days=extra_days)
    dt = datetime.datetime(d.year, d.month, d.day, hours, minutes, secs, tzinfo=KANSAS_CITY_TZ)
    return dt.isoformat()
