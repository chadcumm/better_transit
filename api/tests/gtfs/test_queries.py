"""Tests for GTFS query functions with mocked DB sessions."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from better_transit.gtfs.queries import (
    get_active_service_ids,
    get_route_by_id,
    get_routes,
    get_routes_for_stop,
    get_shape_as_geojson,
    get_shape_id_for_route,
    get_stop_by_id,
    get_stop_times_for_stop,
    get_stops_for_route,
    get_trips_for_route,
)


def _mock_session(execute_return):
    """Create a mock AsyncSession with a preset execute return value."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=execute_return)
    return session


@pytest.mark.asyncio
async def test_get_stop_by_id_returns_none():
    """get_stop_by_id returns None when no stop found."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session = _mock_session(mock_result)

    result = await get_stop_by_id(session, "nonexistent")
    assert result is None
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_stop_by_id_returns_stop():
    mock_stop = MagicMock()
    mock_stop.stop_id = "123"
    mock_stop.stop_name = "Test Stop"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_stop
    session = _mock_session(mock_result)

    result = await get_stop_by_id(session, "123")
    assert result.stop_id == "123"


@pytest.mark.asyncio
async def test_get_routes_returns_list():
    mock_route = MagicMock()
    mock_route.route_id = "101"

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_route]
    mock_result.scalars.return_value = mock_scalars
    session = _mock_session(mock_result)

    result = await get_routes(session)
    assert len(result) == 1
    assert result[0].route_id == "101"


@pytest.mark.asyncio
async def test_get_route_by_id_returns_none():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session = _mock_session(mock_result)

    result = await get_route_by_id(session, "nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_get_active_service_ids():
    """Test service ID resolution from calendar + calendar_dates."""
    # First call: calendar query returns ["WK"]
    cal_result = MagicMock()
    cal_scalars = MagicMock()
    cal_scalars.all.return_value = ["WK"]
    cal_result.scalars.return_value = cal_scalars

    # Second call: calendar_dates query returns no exceptions
    exc_result = MagicMock()
    exc_result.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[cal_result, exc_result])

    # Monday = weekday 0
    result = await get_active_service_ids(session, datetime.date(2026, 3, 2))
    assert result == ["WK"]


@pytest.mark.asyncio
async def test_get_active_service_ids_with_exception_added():
    """Calendar_dates exception_type=1 adds a service."""
    cal_result = MagicMock()
    cal_scalars = MagicMock()
    cal_scalars.all.return_value = ["WK"]
    cal_result.scalars.return_value = cal_scalars

    exc_result = MagicMock()
    exc_result.all.return_value = [("HOLIDAY", 1)]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[cal_result, exc_result])

    result = await get_active_service_ids(session, datetime.date(2026, 3, 2))
    assert sorted(result) == ["HOLIDAY", "WK"]


@pytest.mark.asyncio
async def test_get_active_service_ids_with_exception_removed():
    """Calendar_dates exception_type=2 removes a service."""
    cal_result = MagicMock()
    cal_scalars = MagicMock()
    cal_scalars.all.return_value = ["WK"]
    cal_result.scalars.return_value = cal_scalars

    exc_result = MagicMock()
    exc_result.all.return_value = [("WK", 2)]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[cal_result, exc_result])

    result = await get_active_service_ids(session, datetime.date(2026, 3, 2))
    assert result == []


@pytest.mark.asyncio
async def test_get_stop_times_for_stop():
    """Test stop times query returns formatted dicts."""
    mock_stop_time = MagicMock()
    mock_stop_time.trip_id = "T1"
    mock_stop_time.arrival_time = "08:00:00"
    mock_stop_time.departure_time = "08:01:00"
    mock_stop_time.stop_sequence = 5

    mock_row = MagicMock()
    mock_row.StopTime = mock_stop_time
    mock_row.route_id = "101"
    mock_row.trip_headsign = "Downtown"

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    session = _mock_session(mock_result)

    result = await get_stop_times_for_stop(session, "S1", ["WK"])
    assert len(result) == 1
    assert result[0]["trip_id"] == "T1"
    assert result[0]["route_id"] == "101"
    assert result[0]["headsign"] == "Downtown"


@pytest.mark.asyncio
async def test_get_shape_id_for_route():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "S1"
    session = _mock_session(mock_result)

    result = await get_shape_id_for_route(session, "101")
    assert result == "S1"


@pytest.mark.asyncio
async def test_get_shape_as_geojson():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = '{"type":"LineString"}'
    session = _mock_session(mock_result)

    result = await get_shape_as_geojson(session, "S1")
    assert result == '{"type":"LineString"}'


@pytest.mark.asyncio
async def test_get_stops_for_route():
    # First call: get a trip_id
    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = "T1"

    # Second call: get stops for that trip
    mock_row = MagicMock()
    mock_row.stop_id = "1"
    mock_row.stop_name = "First St"
    mock_row.stop_lat = 39.09
    mock_row.stop_lon = -94.57
    mock_row.stop_sequence = 1
    mock_row.arrival_time = "08:00:00"
    mock_row.departure_time = "08:01:00"

    stops_result = MagicMock()
    stops_result.all.return_value = [mock_row]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[trip_result, stops_result])

    result = await get_stops_for_route(session, "101", ["WK"])
    assert len(result) == 1
    assert result[0]["stop_id"] == "1"


@pytest.mark.asyncio
async def test_get_stops_for_route_no_trips():
    trip_result = MagicMock()
    trip_result.scalar_one_or_none.return_value = None
    session = _mock_session(trip_result)

    result = await get_stops_for_route(session, "101", ["WK"])
    assert result == []


@pytest.mark.asyncio
async def test_get_routes_for_stop():
    mock_row = MagicMock()
    mock_row.route_id = "101"
    mock_row.route_short_name = "101"
    mock_row.route_long_name = "State"

    mock_result = MagicMock()
    mock_result.all.return_value = [mock_row]
    session = _mock_session(mock_result)

    result = await get_routes_for_stop(session, "S1")
    assert len(result) == 1
    assert result[0]["route_id"] == "101"
    assert result[0]["route_short_name"] == "101"


@pytest.mark.asyncio
async def test_get_trips_for_route():
    mock_trip = MagicMock()
    mock_trip.trip_id = "T1"

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_trip]
    mock_result.scalars.return_value = mock_scalars
    session = _mock_session(mock_result)

    result = await get_trips_for_route(session, "101", ["WK"])
    assert len(result) == 1
    assert result[0].trip_id == "T1"
