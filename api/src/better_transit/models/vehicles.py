from pydantic import BaseModel


class VehiclePositionResponse(BaseModel):
    vehicle_id: str
    trip_id: str | None = None
    route_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timestamp: str | None = None
