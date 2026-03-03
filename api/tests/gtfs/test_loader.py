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
