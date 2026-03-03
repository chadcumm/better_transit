from pydantic import BaseModel, field_validator


def _empty_to_none(v: str | None) -> str | None:
    if isinstance(v, str) and v.strip() == "":
        return None
    return v


class AgencyRow(BaseModel):
    agency_id: str
    agency_name: str
    agency_url: str
    agency_timezone: str
    agency_lang: str | None = None
    agency_phone: str | None = None
    agency_fare_url: str | None = None

    _clean = field_validator(
        "agency_lang", "agency_phone", "agency_fare_url", mode="before"
    )(_empty_to_none)


class RouteRow(BaseModel):
    route_id: str
    agency_id: str
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_desc: str | None = None
    route_type: int
    route_url: str | None = None
    route_color: str | None = None
    route_text_color: str | None = None

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
    stop_id: str
    stop_code: str | None = None
    stop_name: str
    stop_desc: str | None = None
    stop_lat: float
    stop_lon: float
    zone_id: str | None = None
    stop_url: str | None = None
    location_type: int | None = None
    parent_station: str | None = None
    stop_timezone: str | None = None
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
    route_id: str
    service_id: str
    trip_id: str
    trip_headsign: str | None = None
    trip_short_name: str | None = None
    direction_id: int | None = None
    block_id: str | None = None
    shape_id: str | None = None
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
    trip_id: str
    arrival_time: str
    departure_time: str
    stop_id: str
    stop_sequence: int
    stop_headsign: str | None = None
    pickup_type: int | None = None
    drop_off_type: int | None = None
    shape_dist_traveled: float | None = None
    timepoint: int | None = None

    @field_validator("arrival_time", "departure_time", mode="before")
    @classmethod
    def strip_time(cls, v: str) -> str:
        return v.strip()

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
    service_id: str
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    start_date: str
    end_date: str


class CalendarDateRow(BaseModel):
    service_id: str
    date: str
    exception_type: int


class ShapePointRow(BaseModel):
    shape_id: str
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
