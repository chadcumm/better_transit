import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from better_transit.gtfs.importer import run_import
from better_transit.gtfs.models import Base

TEST_DB_URL = "postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit_test"


@pytest_asyncio.fixture
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
