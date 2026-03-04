from pydantic import BaseModel, Field, field_validator


def _empty_to_none(v: str | None) -> str | None:
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class AgencyRow(BaseModel):
    agency_id: str = Field(max_length=200)
    agency_name: str = Field(max_length=500)
    agency_url: str = Field(max_length=1000)
    agency_timezone: str = Field(max_length=100)
    agency_lang: str | None = Field(default=None, max_length=100)
    agency_phone: str | None = Field(default=None, max_length=100)
    agency_fare_url: str | None = Field(default=None, max_length=1000)

    _clean = field_validator(
        "agency_lang", "agency_phone", "agency_fare_url", mode="before"
    )(_empty_to_none)


class RouteRow(BaseModel):
    route_id: str = Field(max_length=200)
    agency_id: str = Field(max_length=200)
    route_short_name: str | None = Field(default=None, max_length=200)
    route_long_name: str | None = Field(default=None, max_length=500)
    route_desc: str | None = Field(default=None, max_length=1000)
    route_type: int
    route_url: str | None = Field(default=None, max_length=1000)
    route_color: str | None = Field(default=None, max_length=10)
    route_text_color: str | None = Field(default=None, max_length=10)

    _clean = field_validator(
        "route_short_name",
        "route_long_name",
        "route_desc",
        "route_url",
        "route_color",
        "route_text_color",
        mode="before",
    )(_empty_to_none)


class StopRow(BaseModel):
    stop_id: str = Field(max_length=200)
    stop_code: str | None = Field(default=None, max_length=200)
    stop_name: str = Field(max_length=500)
    stop_desc: str | None = Field(default=None, max_length=1000)
    stop_lat: float
    stop_lon: float
    zone_id: str | None = Field(default=None, max_length=200)
    stop_url: str | None = Field(default=None, max_length=1000)
    location_type: int | None = None
    parent_station: str | None = Field(default=None, max_length=200)
    stop_timezone: str | None = Field(default=None, max_length=100)
    wheelchair_boarding: int | None = None

    _clean = field_validator(
        "stop_code",
        "stop_desc",
        "zone_id",
        "stop_url",
        "parent_station",
        "stop_timezone",
        mode="before",
    )(_empty_to_none)

    @field_validator("location_type", "wheelchair_boarding", mode="before")
    @classmethod
    def empty_int_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class TripRow(BaseModel):
    route_id: str = Field(max_length=200)
    service_id: str = Field(max_length=200)
    trip_id: str = Field(max_length=200)
    trip_headsign: str | None = Field(default=None, max_length=500)
    trip_short_name: str | None = Field(default=None, max_length=200)
    direction_id: int | None = None
    block_id: str | None = Field(default=None, max_length=200)
    shape_id: str | None = Field(default=None, max_length=200)
    wheelchair_accessible: int | None = None
    bikes_allowed: int | None = None

    _clean = field_validator(
        "trip_headsign",
        "trip_short_name",
        "block_id",
        "shape_id",
        mode="before",
    )(_empty_to_none)

    @field_validator("direction_id", "wheelchair_accessible", "bikes_allowed", mode="before")
    @classmethod
    def empty_int_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class StopTimeRow(BaseModel):
    trip_id: str = Field(max_length=200)
    arrival_time: str = Field(max_length=20)
    departure_time: str = Field(max_length=20)
    stop_id: str = Field(max_length=200)
    stop_sequence: int
    stop_headsign: str | None = Field(default=None, max_length=500)
    pickup_type: int | None = None
    drop_off_type: int | None = None
    shape_dist_traveled: float | None = None
    timepoint: int | None = None

    @field_validator("arrival_time", "departure_time", mode="before")
    @classmethod
    def normalize_time(cls, v: str) -> str:
        v = v.strip()
        # Zero-pad single-digit hours: "5:30:00" -> "05:30:00"
        parts = v.split(":")
        if len(parts) == 3 and len(parts[0]) == 1:
            v = f"0{v}"
        return v

    _clean = field_validator("stop_headsign", mode="before")(_empty_to_none)

    @field_validator(
        "pickup_type", "drop_off_type", "timepoint", mode="before"
    )
    @classmethod
    def empty_int_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator("shape_dist_traveled", mode="before")
    @classmethod
    def empty_float_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v


class CalendarRow(BaseModel):
    service_id: str = Field(max_length=200)
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: str = Field(max_length=8)
    end_date: str = Field(max_length=8)


class CalendarDateRow(BaseModel):
    service_id: str = Field(max_length=200)
    date: str = Field(max_length=8)
    exception_type: int


class ShapePointRow(BaseModel):
    shape_id: str = Field(max_length=200)
    shape_pt_lat: float
    shape_pt_lon: float
    shape_pt_sequence: int
    shape_dist_traveled: float | None = None

    @field_validator("shape_dist_traveled", mode="before")
    @classmethod
    def empty_float_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
