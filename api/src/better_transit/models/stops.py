from pydantic import BaseModel

from better_transit.models.arrivals import ArrivalResponse


class StopResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float


class StopRouteResponse(BaseModel):
    route_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None


class NearbyStopResponse(BaseModel):
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
    distance_meters: float
    routes: list[StopRouteResponse] = []
    next_arrivals: list[ArrivalResponse] = []
