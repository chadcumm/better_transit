import datetime
from unittest.mock import AsyncMock, patch

import pytest

from better_transit.routing.builder import get_raptor_data, _raptor_cache


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the RAPTOR cache before each test."""
    _raptor_cache.clear()
    yield
    _raptor_cache.clear()


@pytest.mark.asyncio
@patch("better_transit.routing.builder.build_raptor_data")
async def test_cache_returns_same_data(mock_build):
    """Second call with same date should return cached data, not rebuild."""
    from better_transit.routing.data import RaptorData
    mock_data = RaptorData()
    mock_build.return_value = mock_data

    session = AsyncMock()
    date = datetime.date(2026, 3, 3)

    result1 = await get_raptor_data(session, date)
    result2 = await get_raptor_data(session, date)

    assert result1 is result2
    assert mock_build.call_count == 1  # Only built once


@pytest.mark.asyncio
@patch("better_transit.routing.builder.build_raptor_data")
async def test_cache_rebuilds_for_different_date(mock_build):
    """Different date should trigger a rebuild."""
    from better_transit.routing.data import RaptorData
    mock_build.return_value = RaptorData()

    session = AsyncMock()

    await get_raptor_data(session, datetime.date(2026, 3, 3))
    await get_raptor_data(session, datetime.date(2026, 3, 4))

    assert mock_build.call_count == 2


@pytest.mark.asyncio
@patch("better_transit.routing.builder.build_raptor_data")
@patch("better_transit.routing.builder.time")
async def test_cache_expires_after_ttl(mock_time, mock_build):
    """Cache should expire after CACHE_TTL_SECONDS."""
    from better_transit.routing.data import RaptorData
    mock_build.return_value = RaptorData()

    session = AsyncMock()
    date = datetime.date(2026, 3, 3)

    # First call at time 0
    mock_time.monotonic.return_value = 0.0
    await get_raptor_data(session, date)
    assert mock_build.call_count == 1

    # Second call at time 301 (past TTL of 300)
    mock_time.monotonic.return_value = 301.0
    await get_raptor_data(session, date)
    assert mock_build.call_count == 2
