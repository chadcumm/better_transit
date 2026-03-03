import csv
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from better_transit.gtfs.schemas import (
    AgencyRow,
    CalendarDateRow,
    CalendarRow,
    RouteRow,
    ShapePointRow,
    StopRow,
    StopTimeRow,
    TripRow,
)

logger = logging.getLogger(__name__)

GTFS_FILES: dict[str, type[BaseModel]] = {
    "agency": AgencyRow,
    "routes": RouteRow,
    "stops": StopRow,
    "trips": TripRow,
    "stop_times": StopTimeRow,
    "calendar": CalendarRow,
    "calendar_dates": CalendarDateRow,
    "shapes": ShapePointRow,
}


def _parse_file(filepath: Path, schema: type[BaseModel]) -> list[Any]:
    """Parse a single GTFS CSV file into a list of validated Pydantic models."""
    rows: list[Any] = []
    errors = 0

    with filepath.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, raw_row in enumerate(reader):
            try:
                rows.append(schema.model_validate(raw_row))
            except ValidationError:
                errors += 1
                if errors <= 5:
                    logger.warning("Row %d in %s failed validation", i + 1, filepath.name)

    if errors:
        logger.warning("%d rows failed validation in %s", errors, filepath.name)

    logger.info("Parsed %d rows from %s (%d errors)", len(rows), filepath.name, errors)
    return rows


def parse_gtfs_directory(directory: Path) -> dict[str, list[Any]]:
    """Parse all GTFS CSV files in a directory.

    Returns a dict mapping table name to list of validated Pydantic models.
    """
    result: dict[str, list[Any]] = {}

    for name, schema in GTFS_FILES.items():
        filepath = directory / f"{name}.txt"
        if not filepath.exists():
            logger.warning("GTFS file %s.txt not found, skipping", name)
            result[name] = []
            continue
        result[name] = _parse_file(filepath, schema)

    return result
