import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from better_transit.db import get_session
from better_transit.gtfs.queries import (
    get_active_service_ids,
    get_route_by_id,
    get_routes,
    get_shape_as_geojson,
    get_shape_id_for_route,
    get_stops_for_route,
)
from better_transit.gtfs.time_utils import gtfs_time_to_datetime, now_kansas_city
from better_transit.models.routes import (
    RouteDetailResponse,
    RouteResponse,
    RouteStopResponse,
)
from better_transit.models.vehicles import VehiclePositionResponse
from better_transit.realtime.client import fetch_vehicle_positions

router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("", response_model=list[RouteResponse])
async def list_routes(
    session: AsyncSession = Depends(get_session),
):
    """List all transit routes."""
    routes = await get_routes(session)
    return [
        RouteResponse(
            route_id=r.route_id,
            agency_id=r.agency_id,
            route_short_name=r.route_short_name,
            route_long_name=r.route_long_name,
            route_type=r.route_type,
            route_color=r.route_color,
            route_text_color=r.route_text_color,
        )
        for r in routes
    ]


@router.get("/{route_id}", response_model=RouteDetailResponse)
async def route_detail(
    route_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get route details with shape geometry and stop schedule."""
    route = await get_route_by_id(session, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Shape geometry as GeoJSON
    shape_geojson = None
    shape_id = await get_shape_id_for_route(session, route_id)
    if shape_id:
        geojson_str = await get_shape_as_geojson(session, shape_id)
        if geojson_str:
            shape_geojson = json.loads(geojson_str)

    # Stop schedule from a representative trip
    today = now_kansas_city().date()
    service_ids = await get_active_service_ids(session, today)
    stops = []
    if service_ids:
        stop_dicts = await get_stops_for_route(session, route_id, service_ids)
        stops = [
            RouteStopResponse(
                stop_id=s["stop_id"],
                stop_name=s["stop_name"],
                stop_lat=s["stop_lat"],
                stop_lon=s["stop_lon"],
                stop_sequence=s["stop_sequence"],
                arrival_time=gtfs_time_to_datetime(
                    s["arrival_time"], today
                ).isoformat(),
                departure_time=gtfs_time_to_datetime(
                    s["departure_time"], today
                ).isoformat(),
            )
            for s in stop_dicts
        ]

    return RouteDetailResponse(
        route_id=route.route_id,
        agency_id=route.agency_id,
        route_short_name=route.route_short_name,
        route_long_name=route.route_long_name,
        route_type=route.route_type,
        route_color=route.route_color,
        route_text_color=route.route_text_color,
        shape_geojson=shape_geojson,
        stops=stops,
    )


@router.get("/{route_id}/vehicles", response_model=list[VehiclePositionResponse])
async def route_vehicles(
    route_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get current vehicle positions for a route from GTFS-RT."""
    route = await get_route_by_id(session, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    all_positions = await asyncio.to_thread(fetch_vehicle_positions)
    route_positions = [vp for vp in all_positions if vp.get("route_id") == route_id]

    return [
        VehiclePositionResponse(
            vehicle_id=vp["vehicle_id"],
            trip_id=vp.get("trip_id"),
            route_id=vp.get("route_id"),
            latitude=vp.get("latitude"),
            longitude=vp.get("longitude"),
            timestamp=vp.get("timestamp"),
        )
        for vp in route_positions
    ]
