from sqlalchemy import inspect

from better_transit.gtfs.models import (
    Agency,
    Base,
    Calendar,
    CalendarDate,
    Route,
    ShapeGeom,
    ShapePoint,
    Stop,
    StopTime,
    Trip,
)


def test_all_models_have_tablenames():
    assert Agency.__tablename__ == "agency"
    assert Route.__tablename__ == "routes"
    assert Stop.__tablename__ == "stops"
    assert Trip.__tablename__ == "trips"
    assert StopTime.__tablename__ == "stop_times"
    assert Calendar.__tablename__ == "calendar"
    assert CalendarDate.__tablename__ == "calendar_dates"
    assert ShapePoint.__tablename__ == "shapes"
    assert ShapeGeom.__tablename__ == "shape_geoms"


def test_stop_has_geometry_column():
    mapper = inspect(Stop)
    columns = {c.key for c in mapper.columns}
    assert "geom" in columns


def test_shape_geom_has_geometry_column():
    mapper = inspect(ShapeGeom)
    columns = {c.key for c in mapper.columns}
    assert "geom" in columns


def test_base_metadata_has_all_tables():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "agency",
        "routes",
        "stops",
        "trips",
        "stop_times",
        "calendar",
        "calendar_dates",
        "shapes",
        "shape_geoms",
    }
    assert expected.issubset(table_names)
