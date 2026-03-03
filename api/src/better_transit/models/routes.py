from typing import Any

from pydantic import BaseModel


class RouteResponse(BaseModel):
    route_id: str
    agency_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_type: int
    route_color: str | None = None
    route_text_color: str | None = None


class RouteStopResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    stop_sequence: int
    arrival_time: str
    departure_time: str


class RouteDetailResponse(RouteResponse):
    shape_geojson: dict[str, Any] | None = None
    stops: list[RouteStopResponse] = []
