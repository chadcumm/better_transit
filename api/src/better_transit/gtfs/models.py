from geoalchemy2 import Geometry
from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Agency(Base):
    __tablename__ = "agency"

    agency_id: Mapped[str] = mapped_column(String, primary_key=True)
    agency_name: Mapped[str] = mapped_column(String, nullable=False)
    agency_url: Mapped[str] = mapped_column(String, nullable=False)
    agency_timezone: Mapped[str] = mapped_column(String, nullable=False)
    agency_lang: Mapped[str | None] = mapped_column(String)
    agency_phone: Mapped[str | None] = mapped_column(String)
    agency_fare_url: Mapped[str | None] = mapped_column(String)


class Route(Base):
    __tablename__ = "routes"

    route_id: Mapped[str] = mapped_column(String, primary_key=True)
    agency_id: Mapped[str] = mapped_column(String, nullable=False)
    route_short_name: Mapped[str | None] = mapped_column(String)
    route_long_name: Mapped[str | None] = mapped_column(String)
    route_desc: Mapped[str | None] = mapped_column(String)
    route_type: Mapped[int] = mapped_column(Integer, nullable=False)
    route_url: Mapped[str | None] = mapped_column(String)
    route_color: Mapped[str | None] = mapped_column(String)
    route_text_color: Mapped[str | None] = mapped_column(String)


class Stop(Base):
    __tablename__ = "stops"

    stop_id: Mapped[str] = mapped_column(String, primary_key=True)
    stop_code: Mapped[str | None] = mapped_column(String)
    stop_name: Mapped[str] = mapped_column(String, nullable=False)
    stop_desc: Mapped[str | None] = mapped_column(String)
    stop_lat: Mapped[float] = mapped_column(Float, nullable=False)
    stop_lon: Mapped[float] = mapped_column(Float, nullable=False)
    zone_id: Mapped[str | None] = mapped_column(String)
    stop_url: Mapped[str | None] = mapped_column(String)
    location_type: Mapped[int | None] = mapped_column(Integer)
    parent_station: Mapped[str | None] = mapped_column(String)
    stop_timezone: Mapped[str | None] = mapped_column(String)
    wheelchair_boarding: Mapped[int | None] = mapped_column(Integer)
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=True)

    __table_args__ = (
        Index("ix_stops_geom", "geom", postgresql_using="gist"),
    )


class Trip(Base):
    __tablename__ = "trips"

    trip_id: Mapped[str] = mapped_column(String, primary_key=True)
    route_id: Mapped[str] = mapped_column(String, nullable=False)
    service_id: Mapped[str] = mapped_column(String, nullable=False)
    trip_headsign: Mapped[str | None] = mapped_column(String)
    trip_short_name: Mapped[str | None] = mapped_column(String)
    direction_id: Mapped[int | None] = mapped_column(Integer)
    block_id: Mapped[str | None] = mapped_column(String)
    shape_id: Mapped[str | None] = mapped_column(String)
    wheelchair_accessible: Mapped[int | None] = mapped_column(Integer)
    bikes_allowed: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_trips_route_service", "route_id", "service_id"),
    )


class StopTime(Base):
    __tablename__ = "stop_times"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(String, nullable=False)
    arrival_time: Mapped[str] = mapped_column(String, nullable=False)
    departure_time: Mapped[str] = mapped_column(String, nullable=False)
    stop_id: Mapped[str] = mapped_column(String, nullable=False)
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    stop_headsign: Mapped[str | None] = mapped_column(String)
    pickup_type: Mapped[int | None] = mapped_column(Integer)
    drop_off_type: Mapped[int | None] = mapped_column(Integer)
    shape_dist_traveled: Mapped[float | None] = mapped_column(Float)
    timepoint: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_stop_times_stop_departure", "stop_id", "departure_time"),
        Index("ix_stop_times_trip_seq", "trip_id", "stop_sequence"),
    )


class Calendar(Base):
    __tablename__ = "calendar"

    service_id: Mapped[str] = mapped_column(String, primary_key=True)
    monday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tuesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wednesday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    thursday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    friday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    saturday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sunday: Mapped[bool] = mapped_column(Boolean, nullable=False)
    start_date: Mapped[str] = mapped_column(String, nullable=False)
    end_date: Mapped[str] = mapped_column(String, nullable=False)


class CalendarDate(Base):
    __tablename__ = "calendar_dates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    exception_type: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index("ix_calendar_dates_service_date", "service_id", "date"),
    )


class ShapePoint(Base):
    __tablename__ = "shapes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shape_id: Mapped[str] = mapped_column(String, nullable=False)
    shape_pt_lat: Mapped[float] = mapped_column(Float, nullable=False)
    shape_pt_lon: Mapped[float] = mapped_column(Float, nullable=False)
    shape_pt_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    shape_dist_traveled: Mapped[float | None] = mapped_column(Float)


class ShapeGeom(Base):
    __tablename__ = "shape_geoms"

    shape_id: Mapped[str] = mapped_column(String, primary_key=True)
    geom = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326), nullable=False
    )
