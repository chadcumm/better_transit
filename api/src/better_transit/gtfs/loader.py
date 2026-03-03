import logging
from collections import defaultdict
from typing import Any

from geoalchemy2 import WKTElement
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

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
from better_transit.gtfs.schemas import ShapePointRow, StopRow

logger = logging.getLogger(__name__)

# Order matters for truncation (reverse dependency order)
TRUNCATE_ORDER = [
    "shape_geoms",
    "shapes",
    "stop_times",
    "calendar_dates",
    "calendar",
    "trips",
    "stops",
    "routes",
    "agency",
]

TABLE_MAP: dict[str, type[Base]] = {
    "agency": Agency,
    "routes": Route,
    "stops": Stop,
    "trips": Trip,
    "stop_times": StopTime,
    "calendar": Calendar,
    "calendar_dates": CalendarDate,
    "shapes": ShapePoint,
}


def _stop_to_dict(row: StopRow) -> dict[str, Any]:
    """Convert a StopRow to a dict with PostGIS geometry."""
    d = row.model_dump()
    d["geom"] = WKTElement(f"POINT({row.stop_lon} {row.stop_lat})", srid=4326)
    return d


def _build_shape_geoms(shape_points: list[ShapePointRow]) -> list[dict[str, Any]]:
    """Aggregate shape points into LINESTRING geometries per shape_id."""
    by_shape: dict[str, list[ShapePointRow]] = defaultdict(list)
    for pt in shape_points:
        by_shape[pt.shape_id].append(pt)

    geoms = []
    for shape_id, points in by_shape.items():
        sorted_pts = sorted(points, key=lambda p: p.shape_pt_sequence)
        if len(sorted_pts) < 2:
            logger.warning("Shape %s has < 2 points, skipping", shape_id)
            continue
        coords = ", ".join(f"{p.shape_pt_lon} {p.shape_pt_lat}" for p in sorted_pts)
        wkt = f"LINESTRING({coords})"
        geoms.append({"shape_id": shape_id, "geom": WKTElement(wkt, srid=4326)})

    return geoms


async def load_gtfs_data(
    engine: AsyncEngine, data: dict[str, list[Any]]
) -> dict[str, int]:
    """Load parsed GTFS data into the database.

    Truncates all tables and bulk inserts. Returns row counts per table.
    """
    stats: dict[str, int] = {}

    async with engine.begin() as conn:
        # Truncate all tables
        for table_name in TRUNCATE_ORDER:
            await conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
        logger.info("Truncated all GTFS tables")

        # Insert each table
        for name, model_cls in TABLE_MAP.items():
            rows = data.get(name, [])
            if not rows:
                stats[name] = 0
                continue

            if name == "stops":
                dicts = [_stop_to_dict(r) for r in rows]
            else:
                dicts = [r.model_dump() for r in rows]

            await conn.execute(model_cls.__table__.insert(), dicts)
            stats[name] = len(dicts)
            logger.info("Inserted %d rows into %s", len(dicts), name)

        # Build and insert shape geometries
        shape_points = data.get("shapes", [])
        shape_geoms = _build_shape_geoms(shape_points)
        if shape_geoms:
            await conn.execute(ShapeGeom.__table__.insert(), shape_geoms)
        stats["shape_geoms"] = len(shape_geoms)
        logger.info("Inserted %d shape geometries", len(shape_geoms))

    return stats
