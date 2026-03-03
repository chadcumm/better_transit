# GTFS Static Importer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a pipeline that downloads KCATA's GTFS static feed, parses CSV files into validated models, and loads them into PostgreSQL + PostGIS.

**Architecture:** The importer is a CLI-invokable pipeline in `api/src/better_transit/gtfs/`. It downloads a ZIP, parses 8 GTFS CSV files through Pydantic validation, truncates existing tables inside a transaction, and bulk inserts all records. SQLAlchemy + GeoAlchemy2 handle the database layer with Alembic for migrations.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x (async), asyncpg, GeoAlchemy2, Alembic, Pydantic v2, Pydantic Settings, Shapely, PostGIS 3.4 (Docker)

**GTFS data reference (real KCATA feed):**
- `agency.txt` — 1 row, fields: agency_id, agency_name, agency_url, agency_timezone, agency_lang, agency_phone, agency_fare_url
- `routes.txt` — 36 rows, fields: route_id, agency_id, route_short_name, route_long_name, route_desc, route_type, route_url, route_color, route_text_color
- `stops.txt` — 2,668 rows, fields: stop_id, stop_code, stop_name, stop_desc, stop_lat, stop_lon, zone_id, stop_url, location_type, parent_station, stop_timezone, wheelchair_boarding
- `trips.txt` — 5,002 rows, fields: route_id, service_id, trip_id, trip_headsign, trip_short_name, direction_id, block_id, shape_id, wheelchair_accessible, bikes_allowed
- `stop_times.txt` — 187,753 rows, fields: trip_id, arrival_time, departure_time, stop_id, stop_sequence, stop_headsign, pickup_type, drop_off_type, shape_dist_traveled, timepoint
- `calendar.txt` — 3 rows, fields: service_id, monday-sunday, start_date, end_date
- `calendar_dates.txt` — 34 rows, fields: service_id, date, exception_type
- `shapes.txt` — 44,200 rows (100 unique shape_ids), fields: shape_id, shape_pt_lat, shape_pt_lon, shape_pt_sequence, shape_dist_traveled
- `feed_info.txt` — 1 row (metadata only, not imported to DB)

**Data quirks:**
- Times in `stop_times.txt` have leading spaces (` 5:30:00`)
- Times can exceed 24:00:00 for overnight trips (4,509 rows with `24:xx`, 3,538 with `25:xx`)
- Many optional fields are empty strings
- Dates are `YYYYMMDD` format (not ISO)

---

## Task 1: Add dependencies and Docker Compose

**Files:**
- Modify: `api/pyproject.toml`
- Create: `docker-compose.yml` (project root)
- Create: `api/.env` (local dev config)

**Step 1: Add new dependencies to pyproject.toml**

Add to `[project] dependencies`:
```toml
dependencies = [
    "fastapi>=0.115.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "uvicorn>=0.34.0",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "geoalchemy2>=0.15.0",
    "shapely>=2.0",
]
```

**Step 2: Create docker-compose.yml at project root**

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: better_transit
      POSTGRES_USER: better_transit
      POSTGRES_PASSWORD: dev
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

**Step 3: Create api/.env**

```
DATABASE_URL=postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit
GTFS_STATIC_URL=http://www.kc-metro.com/gtf/google_transit.zip
```

**Step 4: Run `uv sync` to install new dependencies**

Run: `cd api && uv sync --all-extras`
Expected: all packages install successfully

**Step 5: Start the database**

Run: `docker compose up -d`
Expected: PostGIS container starts on port 5432

**Step 6: Verify database connection**

Run: `docker compose exec db psql -U better_transit -c "SELECT PostGIS_Version();"`
Expected: prints PostGIS version (3.4.x)

**Step 7: Commit**

```bash
git add api/pyproject.toml api/uv.lock docker-compose.yml api/.env
git commit -m "feat: add database dependencies and Docker Compose for PostGIS"
```

Note: `.env` is gitignored for production, but this one has only local dev defaults so it's fine to commit. If the user prefers, can add `api/.env` to `.gitignore` and use `.env.example` instead.

---

## Task 2: Config and database setup

**Files:**
- Create: `api/src/better_transit/config.py`
- Create: `api/src/better_transit/db.py`
- Test: `api/tests/test_config.py`

**Step 1: Write the failing test for config**

Create `api/tests/test_config.py`:
```python
import os

from better_transit.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert "better_transit" in settings.database_url
    assert "google_transit.zip" in settings.gtfs_static_url


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
    monkeypatch.setenv("GTFS_STATIC_URL", "http://example.com/feed.zip")
    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://test:test@localhost/test"
    assert settings.gtfs_static_url == "http://example.com/feed.zip"
```

**Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'better_transit.config'`

**Step 3: Implement config.py**

Create `api/src/better_transit/config.py`:
```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit"
    )
    gtfs_static_url: str = "http://www.kc-metro.com/gtf/google_transit.zip"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
```

**Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/test_config.py -v`
Expected: 2 tests PASS

**Step 5: Implement db.py**

Create `api/src/better_transit/db.py`:
```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from better_transit.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
```

**Step 6: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 7: Commit**

```bash
git add api/src/better_transit/config.py api/src/better_transit/db.py api/tests/test_config.py
git commit -m "feat: add config (Pydantic Settings) and database engine setup"
```

---

## Task 3: Pydantic schemas for GTFS CSV rows

**Files:**
- Create: `api/src/better_transit/gtfs/schemas.py`
- Test: `api/tests/gtfs/__init__.py`
- Test: `api/tests/gtfs/test_schemas.py`

**Step 1: Write the failing tests**

Create `api/tests/gtfs/__init__.py` (empty).

Create `api/tests/gtfs/test_schemas.py`:
```python
import pytest
from pydantic import ValidationError

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


class TestAgencyRow:
    def test_valid(self):
        row = AgencyRow(
            agency_id="KCATA",
            agency_name="Kansas City Area Transportation Authority",
            agency_url="http://www.kcata.org",
            agency_timezone="America/Chicago",
        )
        assert row.agency_id == "KCATA"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            AgencyRow(agency_id="KCATA")


class TestStopRow:
    def test_valid(self):
        row = StopRow(
            stop_id="1161406",
            stop_name="ON N 110TH ST AT VILLAGE WEST APTS SB",
            stop_lat=39.127334,
            stop_lon=-94.835239,
        )
        assert row.stop_id == "1161406"
        assert row.stop_lat == pytest.approx(39.127334)

    def test_optional_fields_default_none(self):
        row = StopRow(
            stop_id="1",
            stop_name="Test Stop",
            stop_lat=39.0,
            stop_lon=-94.0,
        )
        assert row.stop_code is None
        assert row.location_type is None
        assert row.parent_station is None

    def test_empty_strings_become_none(self):
        row = StopRow(
            stop_id="1",
            stop_name="Test Stop",
            stop_lat=39.0,
            stop_lon=-94.0,
            stop_code="",
            parent_station="",
        )
        assert row.stop_code is None
        assert row.parent_station is None


class TestRouteRow:
    def test_valid(self):
        row = RouteRow(
            route_id="101",
            agency_id="KCATA",
            route_short_name="101",
            route_long_name="State",
            route_type=3,
        )
        assert row.route_id == "101"
        assert row.route_type == 3


class TestTripRow:
    def test_valid(self):
        row = TripRow(
            route_id="101",
            service_id="25.0.1",
            trip_id="285265",
            direction_id=0,
            shape_id="4819",
        )
        assert row.trip_id == "285265"


class TestStopTimeRow:
    def test_valid(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time="5:30:00",
            departure_time="5:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "5:30:00"

    def test_leading_space_stripped(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time=" 5:30:00",
            departure_time=" 5:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "5:30:00"

    def test_overnight_time(self):
        row = StopTimeRow(
            trip_id="285265",
            arrival_time="25:30:00",
            departure_time="25:30:00",
            stop_id="217",
            stop_sequence=1,
        )
        assert row.arrival_time == "25:30:00"


class TestCalendarRow:
    def test_valid(self):
        row = CalendarRow(
            service_id="25.0.1",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date="20260215",
            end_date="20260404",
        )
        assert row.service_id == "25.0.1"
        assert row.monday is True
        assert row.saturday is False

    def test_int_booleans(self):
        row = CalendarRow(
            service_id="25.0.1",
            monday=1,
            tuesday=0,
            wednesday=1,
            thursday=0,
            friday=1,
            saturday=0,
            sunday=0,
            start_date="20260215",
            end_date="20260404",
        )
        assert row.monday is True
        assert row.tuesday is False


class TestCalendarDateRow:
    def test_valid(self):
        row = CalendarDateRow(
            service_id="25.39.1",
            date="20260217",
            exception_type=1,
        )
        assert row.exception_type == 1


class TestShapePointRow:
    def test_valid(self):
        row = ShapePointRow(
            shape_id="4819",
            shape_pt_lat=39.099234,
            shape_pt_lon=-94.573962,
            shape_pt_sequence=1,
            shape_dist_traveled=0.0,
        )
        assert row.shape_id == "4819"
```

**Step 2: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/gtfs/test_schemas.py -v`
Expected: FAIL — cannot import schemas

**Step 3: Implement schemas.py**

Create `api/src/better_transit/gtfs/schemas.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd api && uv run pytest tests/gtfs/test_schemas.py -v`
Expected: all tests PASS

**Step 5: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 6: Commit**

```bash
git add api/src/better_transit/gtfs/schemas.py api/tests/gtfs/
git commit -m "feat: add Pydantic schemas for GTFS CSV row validation"
```

---

## Task 4: SQLAlchemy table models

**Files:**
- Create: `api/src/better_transit/gtfs/models.py`
- Test: `api/tests/gtfs/test_models.py`

**Step 1: Write the failing test**

Create `api/tests/gtfs/test_models.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/gtfs/test_models.py -v`
Expected: FAIL — cannot import models

**Step 3: Implement models.py**

Create `api/src/better_transit/gtfs/models.py`:
```python
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
```

**Step 4: Run tests to verify they pass**

Run: `cd api && uv run pytest tests/gtfs/test_models.py -v`
Expected: all tests PASS

**Step 5: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 6: Commit**

```bash
git add api/src/better_transit/gtfs/models.py api/tests/gtfs/test_models.py
git commit -m "feat: add SQLAlchemy models for GTFS tables with PostGIS geometry"
```

---

## Task 5: Alembic migration setup and initial migration

**Files:**
- Create: `api/alembic.ini`
- Create: `api/migrations/env.py`
- Create: `api/migrations/script.py.mako`
- Create: `api/migrations/versions/` (directory)

**Step 1: Initialize Alembic**

Run: `cd api && uv run alembic init migrations`
Expected: Creates `alembic.ini` and `migrations/` directory

**Step 2: Edit alembic.ini — set sqlalchemy.url to empty (we'll use env.py)**

In `api/alembic.ini`, set:
```ini
sqlalchemy.url =
```

**Step 3: Edit migrations/env.py**

Replace the generated `migrations/env.py` with:
```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from better_transit.config import settings
from better_transit.gtfs.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        settings.database_url, poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 4: Generate the initial migration**

Run: `cd api && uv run alembic revision --autogenerate -m "initial gtfs tables"`
Expected: Creates a migration file in `migrations/versions/`

**Step 5: Run the migration against the local database**

Run: `cd api && uv run alembic upgrade head`
Expected: All tables created. Output includes "Running upgrade ... -> ..., initial gtfs tables"

**Step 6: Verify tables exist**

Run: `docker compose exec db psql -U better_transit -c "\dt"`
Expected: Lists all 9 tables (agency, routes, stops, trips, stop_times, calendar, calendar_dates, shapes, shape_geoms)

**Step 7: Commit**

```bash
git add api/alembic.ini api/migrations/
git commit -m "feat: add Alembic migrations with initial GTFS table schema"
```

---

## Task 6: GTFS downloader

**Files:**
- Create: `api/src/better_transit/gtfs/downloader.py`
- Test: `api/tests/gtfs/test_downloader.py`

**Step 1: Write the failing tests**

Create `api/tests/gtfs/test_downloader.py`:
```python
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from better_transit.gtfs.downloader import download_and_extract


@pytest.fixture
def fake_gtfs_zip(tmp_path: Path) -> Path:
    """Create a minimal fake GTFS zip for testing."""
    zip_path = tmp_path / "fake_gtfs.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("agency.txt", "agency_id,agency_name\nKCATA,Test Agency\n")
        zf.writestr("stops.txt", "stop_id,stop_name\n1,Test Stop\n")
    return zip_path


def test_download_and_extract(fake_gtfs_zip: Path, tmp_path: Path):
    fake_url = f"file://{fake_gtfs_zip}"

    with patch("better_transit.gtfs.downloader.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(fake_gtfs_zip), None)
        result_dir = download_and_extract(fake_url, tmp_path / "output")

    assert result_dir.is_dir()
    assert (result_dir / "agency.txt").exists()
    assert (result_dir / "stops.txt").exists()


def test_download_and_extract_returns_path_with_txt_files(fake_gtfs_zip: Path, tmp_path: Path):
    with patch("better_transit.gtfs.downloader.urllib.request.urlretrieve") as mock_retrieve:
        mock_retrieve.return_value = (str(fake_gtfs_zip), None)
        result_dir = download_and_extract("http://example.com/gtfs.zip", tmp_path / "output")

    txt_files = list(result_dir.glob("*.txt"))
    assert len(txt_files) == 2
```

**Step 2: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/gtfs/test_downloader.py -v`
Expected: FAIL — cannot import downloader

**Step 3: Implement downloader.py**

Create `api/src/better_transit/gtfs/downloader.py`:
```python
import logging
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)


def download_and_extract(url: str, extract_to: Path) -> Path:
    """Download a GTFS ZIP from url and extract to extract_to directory.

    Returns the path to the directory containing extracted .txt files.
    """
    extract_to.mkdir(parents=True, exist_ok=True)
    zip_path = extract_to / "gtfs.zip"

    logger.info("Downloading GTFS feed from %s", url)
    urllib.request.urlretrieve(url, zip_path)

    logger.info("Extracting to %s", extract_to)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_to)

    zip_path.unlink()
    logger.info("Extracted %d files", len(list(extract_to.glob("*.txt"))))
    return extract_to
```

**Step 4: Run tests to verify they pass**

Run: `cd api && uv run pytest tests/gtfs/test_downloader.py -v`
Expected: 2 tests PASS

**Step 5: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 6: Commit**

```bash
git add api/src/better_transit/gtfs/downloader.py api/tests/gtfs/test_downloader.py
git commit -m "feat: add GTFS ZIP downloader and extractor"
```

---

## Task 7: GTFS CSV parser

**Files:**
- Create: `api/src/better_transit/gtfs/parser.py`
- Test: `api/tests/gtfs/test_parser.py`
- Create: `api/tests/gtfs/fixtures/` (directory with sample CSVs)

**Step 1: Create test fixtures**

Create directory `api/tests/gtfs/fixtures/`.

Create `api/tests/gtfs/fixtures/agency.txt`:
```
agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone,agency_fare_url
KCATA,Kansas City Area Transportation Authority,http://www.kcata.org,America/Chicago,en,816-221-0660,
```

Create `api/tests/gtfs/fixtures/stops.txt`:
```
stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id,stop_url,location_type,parent_station,stop_timezone,wheelchair_boarding
1161406,1161406,ON N 110TH ST AT VILLAGE WEST APTS SB,,39.127334,-94.835239,,,,,,0
1161403,1161403,ON N 110TH ST NEAR NTB NB,,39.127996,-94.835108,,,,,,0
```

Create `api/tests/gtfs/fixtures/routes.txt`:
```
route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color
101,KCATA,101,State,101,3,,C0C0C0,000000
102,KCATA,102,Blue Ridge,102,3,,C0C0C0,000000
```

Create `api/tests/gtfs/fixtures/stop_times.txt`:
```
trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled,timepoint
285265, 5:30:00, 5:30:00,217,1,,0,0,,1
285265, 5:30:57, 5:30:57,1090042,2,,0,0,0.3692,0
```

Create `api/tests/gtfs/fixtures/trips.txt`:
```
route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible,bikes_allowed
101,25.0.1,285265,101-STATE AVE / TO VILLAGE WEST,,0,16642,4819,0,0
```

Create `api/tests/gtfs/fixtures/calendar.txt`:
```
service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
25.0.1,1,1,1,1,1,0,0,20260215,20260404
```

Create `api/tests/gtfs/fixtures/calendar_dates.txt`:
```
service_id,date,exception_type
25.39.1,20260217,1
```

Create `api/tests/gtfs/fixtures/shapes.txt`:
```
shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled
4819,39.099234,-94.573962,1,0.0
4819,39.099617,-94.573939,2,0.043
4820,39.100036,-94.573924,1,0.0
4820,39.100437,-94.573909,2,0.1341
```

**Step 2: Write the failing tests**

Create `api/tests/gtfs/test_parser.py`:
```python
from pathlib import Path

import pytest

from better_transit.gtfs.parser import parse_gtfs_directory
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

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_gtfs_directory():
    result = parse_gtfs_directory(FIXTURES)
    assert "agency" in result
    assert "stops" in result
    assert "routes" in result
    assert "trips" in result
    assert "stop_times" in result
    assert "calendar" in result
    assert "calendar_dates" in result
    assert "shapes" in result


def test_parse_agency():
    result = parse_gtfs_directory(FIXTURES)
    agencies = result["agency"]
    assert len(agencies) == 1
    assert isinstance(agencies[0], AgencyRow)
    assert agencies[0].agency_id == "KCATA"


def test_parse_stops():
    result = parse_gtfs_directory(FIXTURES)
    stops = result["stops"]
    assert len(stops) == 2
    assert isinstance(stops[0], StopRow)
    assert stops[0].stop_id == "1161406"
    assert stops[0].stop_lat == pytest.approx(39.127334)


def test_parse_routes():
    result = parse_gtfs_directory(FIXTURES)
    routes = result["routes"]
    assert len(routes) == 2
    assert isinstance(routes[0], RouteRow)


def test_parse_stop_times_strips_leading_space():
    result = parse_gtfs_directory(FIXTURES)
    stop_times = result["stop_times"]
    assert len(stop_times) == 2
    assert isinstance(stop_times[0], StopTimeRow)
    assert stop_times[0].arrival_time == "5:30:00"  # leading space stripped


def test_parse_shapes():
    result = parse_gtfs_directory(FIXTURES)
    shapes = result["shapes"]
    assert len(shapes) == 4
    assert isinstance(shapes[0], ShapePointRow)


def test_parse_calendar():
    result = parse_gtfs_directory(FIXTURES)
    cal = result["calendar"]
    assert len(cal) == 1
    assert isinstance(cal[0], CalendarRow)
    assert cal[0].monday is True
    assert cal[0].saturday is False


def test_parse_calendar_dates():
    result = parse_gtfs_directory(FIXTURES)
    cal_dates = result["calendar_dates"]
    assert len(cal_dates) == 1
    assert isinstance(cal_dates[0], CalendarDateRow)
```

**Step 3: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/gtfs/test_parser.py -v`
Expected: FAIL — cannot import parser

**Step 4: Implement parser.py**

Create `api/src/better_transit/gtfs/parser.py`:
```python
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
```

**Step 5: Run tests to verify they pass**

Run: `cd api && uv run pytest tests/gtfs/test_parser.py -v`
Expected: all tests PASS

**Step 6: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 7: Commit**

```bash
git add api/src/better_transit/gtfs/parser.py api/tests/gtfs/test_parser.py api/tests/gtfs/fixtures/
git commit -m "feat: add GTFS CSV parser with Pydantic validation"
```

---

## Task 8: Database loader

**Files:**
- Create: `api/src/better_transit/gtfs/loader.py`
- Test: `api/tests/gtfs/test_loader.py`

This task requires a running PostGIS database. Tests use the real local database.

**Step 1: Write the failing tests**

Create `api/tests/gtfs/test_loader.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from better_transit.gtfs.loader import load_gtfs_data
from better_transit.gtfs.models import Base
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

TEST_DB_URL = "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit_test"


@pytest.fixture
async def db_session():
    """Create a test database with all tables, yield session, then drop tables."""
    engine = create_async_engine(TEST_DB_URL)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield engine, session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def sample_data():
    return {
        "agency": [
            AgencyRow(
                agency_id="KCATA",
                agency_name="Test Agency",
                agency_url="http://test.com",
                agency_timezone="America/Chicago",
            )
        ],
        "routes": [
            RouteRow(
                route_id="101",
                agency_id="KCATA",
                route_short_name="101",
                route_long_name="State",
                route_type=3,
            )
        ],
        "stops": [
            StopRow(
                stop_id="1",
                stop_name="Test Stop",
                stop_lat=39.1,
                stop_lon=-94.5,
            )
        ],
        "trips": [
            TripRow(
                route_id="101",
                service_id="25.0.1",
                trip_id="T1",
                direction_id=0,
                shape_id="S1",
            )
        ],
        "stop_times": [
            StopTimeRow(
                trip_id="T1",
                arrival_time="8:00:00",
                departure_time="8:00:00",
                stop_id="1",
                stop_sequence=1,
            )
        ],
        "calendar": [
            CalendarRow(
                service_id="25.0.1",
                monday=True,
                tuesday=True,
                wednesday=True,
                thursday=True,
                friday=True,
                saturday=False,
                sunday=False,
                start_date="20260215",
                end_date="20260404",
            )
        ],
        "calendar_dates": [
            CalendarDateRow(
                service_id="25.39.1",
                date="20260217",
                exception_type=1,
            )
        ],
        "shapes": [
            ShapePointRow(
                shape_id="S1",
                shape_pt_lat=39.099234,
                shape_pt_lon=-94.573962,
                shape_pt_sequence=1,
                shape_dist_traveled=0.0,
            ),
            ShapePointRow(
                shape_id="S1",
                shape_pt_lat=39.099617,
                shape_pt_lon=-94.573939,
                shape_pt_sequence=2,
                shape_dist_traveled=0.043,
            ),
        ],
    }


@pytest.mark.asyncio
async def test_load_gtfs_data(db_session, sample_data):
    engine, session_factory = db_session
    stats = await load_gtfs_data(engine, sample_data)

    assert stats["agency"] == 1
    assert stats["routes"] == 1
    assert stats["stops"] == 1
    assert stats["trips"] == 1
    assert stats["stop_times"] == 1
    assert stats["calendar"] == 1
    assert stats["calendar_dates"] == 1
    assert stats["shapes"] == 2
    assert stats["shape_geoms"] == 1


@pytest.mark.asyncio
async def test_load_creates_shape_geom(db_session, sample_data):
    engine, session_factory = db_session
    await load_gtfs_data(engine, sample_data)

    async with session_factory() as session:
        result = await session.execute(text("SELECT shape_id FROM shape_geoms"))
        rows = result.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "S1"


@pytest.mark.asyncio
async def test_load_creates_stop_geometry(db_session, sample_data):
    engine, session_factory = db_session
    await load_gtfs_data(engine, sample_data)

    async with session_factory() as session:
        result = await session.execute(
            text("SELECT ST_AsText(geom) FROM stops WHERE stop_id = '1'")
        )
        row = result.fetchone()
    assert row is not None
    assert "POINT" in row[0]


@pytest.mark.asyncio
async def test_load_is_idempotent(db_session, sample_data):
    """Running load twice should truncate and re-insert, not duplicate."""
    engine, session_factory = db_session
    await load_gtfs_data(engine, sample_data)
    stats = await load_gtfs_data(engine, sample_data)

    assert stats["agency"] == 1

    async with session_factory() as session:
        result = await session.execute(text("SELECT count(*) FROM agency"))
        count = result.scalar()
    assert count == 1
```

**Step 2: Add pytest-asyncio dependency**

Add `"pytest-asyncio>=0.24.0"` to dev dependencies in `pyproject.toml`.

Run: `cd api && uv sync --all-extras`

**Step 3: Create the test database**

Run: `docker compose exec db psql -U better_transit -c "CREATE DATABASE better_transit_test;"`
Run: `docker compose exec db psql -U better_transit_test -d better_transit_test -c "CREATE EXTENSION IF NOT EXISTS postgis;"` — note: this may need to be `psql -U better_transit -d better_transit_test`

**Step 4: Run tests to verify they fail**

Run: `cd api && uv run pytest tests/gtfs/test_loader.py -v`
Expected: FAIL — cannot import loader

**Step 5: Implement loader.py**

Create `api/src/better_transit/gtfs/loader.py`:
```python
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
```

**Step 6: Run tests to verify they pass**

Run: `cd api && uv run pytest tests/gtfs/test_loader.py -v`
Expected: all tests PASS

**Step 7: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 8: Commit**

```bash
git add api/src/better_transit/gtfs/loader.py api/tests/gtfs/test_loader.py api/pyproject.toml api/uv.lock
git commit -m "feat: add database loader with truncate-and-insert and shape aggregation"
```

---

## Task 9: Import orchestrator and CLI entry point

**Files:**
- Create: `api/src/better_transit/gtfs/importer.py`
- Test: `api/tests/gtfs/test_importer.py`

**Step 1: Write the failing test**

Create `api/tests/gtfs/test_importer.py`:
```python
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from better_transit.gtfs.importer import run_import


@pytest.fixture
def fake_gtfs_dir(tmp_path: Path) -> Path:
    """Create a minimal GTFS directory with fixture files."""
    gtfs_dir = tmp_path / "gtfs"
    gtfs_dir.mkdir()

    (gtfs_dir / "agency.txt").write_text(
        "agency_id,agency_name,agency_url,agency_timezone,agency_lang,agency_phone,agency_fare_url\n"
        "KCATA,Kansas City Area Transportation Authority,http://www.kcata.org,America/Chicago,en,816-221-0660,\n"
    )
    (gtfs_dir / "routes.txt").write_text(
        "route_id,agency_id,route_short_name,route_long_name,route_desc,route_type,route_url,route_color,route_text_color\n"
        "101,KCATA,101,State,101,3,,C0C0C0,000000\n"
    )
    (gtfs_dir / "stops.txt").write_text(
        "stop_id,stop_code,stop_name,stop_desc,stop_lat,stop_lon,zone_id,stop_url,location_type,parent_station,stop_timezone,wheelchair_boarding\n"
        "1,1,Test Stop,,39.1,-94.5,,,,,,0\n"
    )
    (gtfs_dir / "trips.txt").write_text(
        "route_id,service_id,trip_id,trip_headsign,trip_short_name,direction_id,block_id,shape_id,wheelchair_accessible,bikes_allowed\n"
        "101,25.0.1,T1,Test,,0,1,S1,0,0\n"
    )
    (gtfs_dir / "stop_times.txt").write_text(
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence,stop_headsign,pickup_type,drop_off_type,shape_dist_traveled,timepoint\n"
        "T1, 8:00:00, 8:00:00,1,1,,0,0,,1\n"
    )
    (gtfs_dir / "calendar.txt").write_text(
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "25.0.1,1,1,1,1,1,0,0,20260215,20260404\n"
    )
    (gtfs_dir / "calendar_dates.txt").write_text(
        "service_id,date,exception_type\n"
        "25.39.1,20260217,1\n"
    )
    (gtfs_dir / "shapes.txt").write_text(
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
        "S1,39.099234,-94.573962,1,0.0\n"
        "S1,39.099617,-94.573939,2,0.043\n"
    )
    return gtfs_dir


@pytest.mark.asyncio
async def test_run_import_orchestrates_pipeline(fake_gtfs_dir: Path):
    mock_engine = AsyncMock()

    with (
        patch("better_transit.gtfs.importer.download_and_extract", return_value=fake_gtfs_dir),
        patch("better_transit.gtfs.importer.load_gtfs_data", new_callable=AsyncMock) as mock_load,
    ):
        mock_load.return_value = {
            "agency": 1,
            "routes": 1,
            "stops": 1,
            "trips": 1,
            "stop_times": 1,
            "calendar": 1,
            "calendar_dates": 1,
            "shapes": 2,
            "shape_geoms": 1,
        }
        stats = await run_import(mock_engine, "http://example.com/gtfs.zip")

    assert stats["agency"] == 1
    assert stats["stops"] == 1
    mock_load.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `cd api && uv run pytest tests/gtfs/test_importer.py -v`
Expected: FAIL — cannot import importer

**Step 3: Implement importer.py**

Create `api/src/better_transit/gtfs/importer.py`:
```python
import asyncio
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from better_transit.config import settings
from better_transit.gtfs.downloader import download_and_extract
from better_transit.gtfs.loader import load_gtfs_data
from better_transit.gtfs.parser import parse_gtfs_directory

logger = logging.getLogger(__name__)


async def run_import(
    engine: AsyncEngine, gtfs_url: str | None = None
) -> dict[str, int]:
    """Run the full GTFS import pipeline.

    1. Download and extract GTFS ZIP
    2. Parse CSV files into validated models
    3. Load into database (truncate + insert)

    Returns row counts per table.
    """
    url = gtfs_url or settings.gtfs_static_url
    start = time.monotonic()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "gtfs"
        logger.info("Starting GTFS import from %s", url)

        # Download and extract
        gtfs_dir = download_and_extract(url, tmp_path)

        # Parse
        logger.info("Parsing GTFS files...")
        data = parse_gtfs_directory(gtfs_dir)

        # Load
        logger.info("Loading into database...")
        stats = await load_gtfs_data(engine, data)

    elapsed = time.monotonic() - start
    logger.info("GTFS import complete in %.1fs", elapsed)
    for table, count in stats.items():
        logger.info("  %s: %d rows", table, count)

    return stats


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    engine = create_async_engine(settings.database_url)
    try:
        await run_import(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
```

**Step 4: Run test to verify it passes**

Run: `cd api && uv run pytest tests/gtfs/test_importer.py -v`
Expected: PASS

**Step 5: Lint**

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 6: Commit**

```bash
git add api/src/better_transit/gtfs/importer.py api/tests/gtfs/test_importer.py
git commit -m "feat: add GTFS import orchestrator with CLI entry point"
```

---

## Task 10: End-to-end integration test with real KCATA data

**Files:**
- Test: `api/tests/gtfs/test_integration.py`

This test downloads the real KCATA feed, parses it, and loads it into the test database. It's slow (~10-15 seconds) so it's marked with a `slow` marker.

**Step 1: Add pytest marker for slow tests**

In `api/pyproject.toml`, under `[tool.pytest.ini_options]`, add:
```toml
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]
```

**Step 2: Write the integration test**

Create `api/tests/gtfs/test_integration.py`:
```python
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from better_transit.gtfs.importer import run_import
from better_transit.gtfs.models import Base

TEST_DB_URL = "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit_test"


@pytest.fixture
async def test_engine():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_full_import_with_real_data(test_engine):
    """Download and import the real KCATA GTFS feed."""
    stats = await run_import(test_engine)

    # Based on known KCATA feed sizes (approximate, allow for updates)
    assert stats["agency"] >= 1
    assert stats["routes"] >= 30
    assert stats["stops"] >= 2000
    assert stats["trips"] >= 4000
    assert stats["stop_times"] >= 100000
    assert stats["calendar"] >= 1
    assert stats["shapes"] >= 40000
    assert stats["shape_geoms"] >= 50

    # Verify spatial data was created
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT count(*) FROM stops WHERE geom IS NOT NULL")
        )
        stops_with_geom = result.scalar()
        assert stops_with_geom == stats["stops"]

        result = await session.execute(
            text("SELECT count(*) FROM shape_geoms WHERE geom IS NOT NULL")
        )
        shapes_with_geom = result.scalar()
        assert shapes_with_geom == stats["shape_geoms"]
```

**Step 3: Run the integration test**

Run: `cd api && uv run pytest tests/gtfs/test_integration.py -v -m slow`
Expected: PASS (takes ~10-15 seconds for download + parse + load)

**Step 4: Verify all tests still pass**

Run: `cd api && uv run pytest -v -m "not slow"`
Expected: All unit tests PASS

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 5: Commit**

```bash
git add api/tests/gtfs/test_integration.py api/pyproject.toml
git commit -m "test: add end-to-end integration test with real KCATA GTFS data"
```

---

## Task 11: Run the real import and verify

This is the final manual verification step.

**Step 1: Run the CLI importer against the real database**

Run: `cd api && uv run python -m better_transit.gtfs.importer`
Expected: Logs showing download, parse, load with row counts. ~5-10 seconds total.

**Step 2: Verify data in the database**

Run:
```bash
docker compose exec db psql -U better_transit -c "
  SELECT 'agency' as t, count(*) FROM agency
  UNION ALL SELECT 'routes', count(*) FROM routes
  UNION ALL SELECT 'stops', count(*) FROM stops
  UNION ALL SELECT 'trips', count(*) FROM trips
  UNION ALL SELECT 'stop_times', count(*) FROM stop_times
  UNION ALL SELECT 'calendar', count(*) FROM calendar
  UNION ALL SELECT 'calendar_dates', count(*) FROM calendar_dates
  UNION ALL SELECT 'shapes', count(*) FROM shapes
  UNION ALL SELECT 'shape_geoms', count(*) FROM shape_geoms
  ORDER BY t;
"
```
Expected: Row counts matching the feed (~1 agency, ~36 routes, ~2668 stops, ~5002 trips, ~187753 stop_times, ~3 calendar, ~34 calendar_dates, ~44200 shapes, ~100 shape_geoms)

**Step 3: Test a spatial query**

Run:
```bash
docker compose exec db psql -U better_transit -c "
  SELECT stop_id, stop_name, ST_AsText(geom)
  FROM stops
  ORDER BY geom <-> ST_SetSRID(ST_MakePoint(-94.5786, 39.0997), 4326)
  LIMIT 5;
"
```
Expected: Returns 5 stops nearest to downtown Kansas City

**Step 4: Run all tests one final time**

Run: `cd api && uv run pytest -v`
Expected: All tests PASS

Run: `cd api && uv run ruff check .`
Expected: All checks passed

**Step 5: Final commit**

If any tweaks were needed during verification, commit them. Otherwise, the task is complete.

---

## Summary

| Task | What It Builds | Key Files |
|------|---------------|-----------|
| 1 | Dependencies + Docker | `pyproject.toml`, `docker-compose.yml` |
| 2 | Config + DB engine | `config.py`, `db.py` |
| 3 | Pydantic schemas | `gtfs/schemas.py` |
| 4 | SQLAlchemy models | `gtfs/models.py` |
| 5 | Alembic migrations | `alembic.ini`, `migrations/` |
| 6 | GTFS downloader | `gtfs/downloader.py` |
| 7 | CSV parser | `gtfs/parser.py` |
| 8 | Database loader | `gtfs/loader.py` |
| 9 | Import orchestrator + CLI | `gtfs/importer.py` |
| 10 | Integration test | `test_integration.py` |
| 11 | Manual verification | (no new files) |
