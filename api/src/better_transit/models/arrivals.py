from pydantic import BaseModel


class ArrivalResponse(BaseModel):
    trip_id: str
    route_id: str
    headsign: str | None = None
    arrival_time: str
    departure_time: str
    scheduled_arrival_time: str | None = None
    scheduled_departure_time: str | None = None
    delay_seconds: int | None = None
    is_realtime: bool = False
