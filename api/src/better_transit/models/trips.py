from pydantic import BaseModel, Field


class TripLeg(BaseModel):
    mode: str  # "walk", "transit", "transfer"
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    route_id: str | None = None
    departure_time: str | None = None
    arrival_time: str | None = None
    duration_seconds: int | None = None


class TripPlanRequest(BaseModel):
    origin_lat: float = Field(ge=-90, le=90)
    origin_lon: float = Field(ge=-180, le=180)
    destination_lat: float = Field(ge=-90, le=90)
    destination_lon: float = Field(ge=-180, le=180)
    departure_time: str | None = None
    max_walking_minutes: int = Field(default=10, ge=1, le=30)
    max_transfers: int = Field(default=2, ge=0, le=5)


class TripPlanResponse(BaseModel):
    legs: list[TripLeg]
    total_duration_seconds: int
    walking_seconds: int
    transfer_count: int
