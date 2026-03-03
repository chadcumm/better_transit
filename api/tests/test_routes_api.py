"""Tests for API route handlers with mocked DB sessions."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from better_transit.db import get_session
from better_transit.main import app


def _override_session(mock_session):
    """Create a dependency override that yields the mock session."""

    async def _get_session():
        yield mock_session

    return _get_session


# --- /alerts ---


def test_list_alerts_returns_empty():
    client = TestClient(app)
    response = client.get("/alerts")
    assert response.status_code == 200
    assert response.json() == []


# --- /trips/plan ---


@patch("better_transit.routes.trips.build_raptor_data")
@patch("better_transit.routes.trips.get_nearby_stops")
def test_plan_trip_no_stops(mock_nearby, mock_raptor):
    """When no nearby stops found, returns empty list."""
    mock_nearby.return_value = []

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.post(
            "/trips/plan",
            json={
                "origin_lat": 39.1,
                "origin_lon": -94.5,
                "destination_lat": 39.11,
                "destination_lon": -94.55,
            },
        )
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


# --- /routes ---


@patch("better_transit.routes.routes.get_routes")
def test_list_routes(mock_get_routes):
    mock_route = MagicMock()
    mock_route.route_id = "101"
    mock_route.agency_id = "KCATA"
    mock_route.route_short_name = "101"
    mock_route.route_long_name = "State"
    mock_route.route_type = 3
    mock_route.route_color = None
    mock_route.route_text_color = None

    mock_get_routes.return_value = [mock_route]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/routes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["route_id"] == "101"
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.routes.get_route_by_id")
def test_route_detail_not_found(mock_get_route):
    mock_get_route.return_value = None

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/routes/nonexistent")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.routes.get_stops_for_route")
@patch("better_transit.routes.routes.get_active_service_ids")
@patch("better_transit.routes.routes.get_shape_as_geojson")
@patch("better_transit.routes.routes.get_shape_id_for_route")
@patch("better_transit.routes.routes.get_route_by_id")
def test_route_detail(
    mock_get_route, mock_shape_id, mock_geojson, mock_services, mock_stops
):
    mock_route = MagicMock()
    mock_route.route_id = "101"
    mock_route.agency_id = "KCATA"
    mock_route.route_short_name = "101"
    mock_route.route_long_name = "State"
    mock_route.route_type = 3
    mock_route.route_color = "FF0000"
    mock_route.route_text_color = "FFFFFF"
    mock_get_route.return_value = mock_route

    mock_shape_id.return_value = "S1"
    mock_geojson.return_value = (
        '{"type":"LineString","coordinates":[[-94.57,39.09],[-94.57,39.10]]}'
    )
    mock_services.return_value = ["WK"]
    mock_stops.return_value = [
        {
            "stop_id": "1",
            "stop_name": "First St",
            "stop_lat": 39.09,
            "stop_lon": -94.57,
            "stop_sequence": 1,
            "arrival_time": "08:00:00",
            "departure_time": "08:01:00",
        }
    ]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/routes/101")
        assert response.status_code == 200
        data = response.json()
        assert data["route_id"] == "101"
        assert data["route_color"] == "FF0000"
        assert data["shape_geojson"]["type"] == "LineString"
        assert len(data["stops"]) == 1
        assert data["stops"][0]["stop_id"] == "1"
    finally:
        app.dependency_overrides.clear()


# --- /stops ---


@patch("better_transit.routes.stops.fetch_trip_updates", return_value=[])
@patch("better_transit.routes.stops.get_stop_times_for_stop")
@patch("better_transit.routes.stops.get_routes_for_stop")
@patch("better_transit.routes.stops.get_active_service_ids")
@patch("better_transit.routes.stops.get_nearby_stops")
def test_nearby_stops(
    mock_nearby, mock_service_ids, mock_routes, mock_stop_times, _mock_rt
):
    mock_nearby.return_value = [
        {
            "stop_id": "1",
            "stop_name": "Test Stop",
            "stop_lat": 39.1,
            "stop_lon": -94.5,
            "distance_meters": 150.0,
        }
    ]
    mock_service_ids.return_value = ["WK"]
    mock_routes.return_value = [
        {"route_id": "101", "route_short_name": "101", "route_long_name": "State"}
    ]
    mock_stop_times.return_value = [
        {
            "trip_id": "T1",
            "route_id": "101",
            "headsign": "Downtown",
            "arrival_time": "08:00:00",
            "departure_time": "08:01:00",
            "stop_sequence": 1,
        }
    ]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/nearby?lat=39.1&lon=-94.5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["stop_id"] == "1"
        assert data[0]["distance_meters"] == 150.0
        assert len(data[0]["routes"]) == 1
        assert data[0]["routes"][0]["route_id"] == "101"
        assert len(data[0]["next_arrivals"]) == 1
        assert data[0]["next_arrivals"][0]["route_id"] == "101"
    finally:
        app.dependency_overrides.clear()


def test_nearby_stops_validates_lat():
    client = TestClient(app)
    response = client.get("/stops/nearby?lat=100&lon=-94.5")
    assert response.status_code == 422


@patch("better_transit.routes.stops.get_stop_by_id")
def test_stop_detail(mock_get_stop):
    mock_stop = MagicMock()
    mock_stop.stop_id = "1"
    mock_stop.stop_name = "Test Stop"
    mock_stop.stop_lat = 39.1
    mock_stop.stop_lon = -94.5
    mock_get_stop.return_value = mock_stop

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/1")
        assert response.status_code == 200
        data = response.json()
        assert data["stop_id"] == "1"
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.stops.get_stop_by_id")
def test_stop_detail_not_found(mock_get_stop):
    mock_get_stop.return_value = None

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/nonexistent")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.stops.fetch_trip_updates", return_value=[])
@patch("better_transit.routes.stops.get_stop_times_for_stop")
@patch("better_transit.routes.stops.get_active_service_ids")
@patch("better_transit.routes.stops.get_stop_by_id")
def test_stop_arrivals(mock_get_stop, mock_service_ids, mock_stop_times, _mock_rt):
    mock_stop = MagicMock()
    mock_stop.stop_id = "1"
    mock_get_stop.return_value = mock_stop

    mock_service_ids.return_value = ["WK"]
    mock_stop_times.return_value = [
        {
            "trip_id": "T1",
            "route_id": "101",
            "headsign": "Downtown",
            "arrival_time": "08:00:00",
            "departure_time": "08:01:00",
            "stop_sequence": 5,
        }
    ]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/1/arrivals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["route_id"] == "101"
        assert data[0]["is_realtime"] is False
        # Times should be ISO 8601 with timezone offset
        assert "T08:00:00" in data[0]["arrival_time"]
        assert "-05:00" in data[0]["arrival_time"] or "-06:00" in data[0]["arrival_time"]
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.stops.get_active_service_ids")
@patch("better_transit.routes.stops.get_stop_by_id")
def test_stop_arrivals_no_services(mock_get_stop, mock_service_ids):
    mock_stop = MagicMock()
    mock_stop.stop_id = "1"
    mock_get_stop.return_value = mock_stop
    mock_service_ids.return_value = []

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/1/arrivals")
        assert response.status_code == 200
        assert response.json() == []
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.stops.fetch_trip_updates")
@patch("better_transit.routes.stops.get_stop_times_for_stop")
@patch("better_transit.routes.stops.get_active_service_ids")
@patch("better_transit.routes.stops.get_stop_by_id")
def test_stop_arrivals_with_realtime(
    mock_get_stop, mock_service_ids, mock_stop_times, mock_rt
):
    """When RT trip update exists, arrival should have is_realtime=True and delay."""
    mock_stop = MagicMock()
    mock_stop.stop_id = "1"
    mock_get_stop.return_value = mock_stop
    mock_service_ids.return_value = ["WK"]
    mock_stop_times.return_value = [
        {
            "trip_id": "T1",
            "route_id": "101",
            "headsign": "Downtown",
            "arrival_time": "08:00:00",
            "departure_time": "08:01:00",
            "stop_sequence": 5,
        }
    ]
    mock_rt.return_value = [
        {
            "trip_id": "T1",
            "route_id": "101",
            "stop_time_updates": [
                {
                    "stop_id": "1",
                    "stop_sequence": 5,
                    "arrival_delay": 120,
                    "departure_delay": 130,
                }
            ],
        }
    ]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/stops/1/arrivals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["is_realtime"] is True
        assert data[0]["delay_seconds"] == 120
        # Scheduled time should still be present
        assert data[0]["scheduled_arrival_time"] is not None
    finally:
        app.dependency_overrides.clear()


# --- /routes/{route_id}/vehicles ---


@patch("better_transit.routes.routes.fetch_vehicle_positions")
@patch("better_transit.routes.routes.get_route_by_id")
def test_route_vehicles(mock_get_route, mock_vp):
    mock_route = MagicMock()
    mock_route.route_id = "101"
    mock_get_route.return_value = mock_route

    mock_vp.return_value = [
        {
            "vehicle_id": "BUS-42",
            "trip_id": "T1",
            "route_id": "101",
            "latitude": 39.1,
            "longitude": -94.5,
            "timestamp": 1709337600,
        },
        {
            "vehicle_id": "BUS-99",
            "trip_id": "T2",
            "route_id": "202",
            "latitude": 39.2,
            "longitude": -94.6,
            "timestamp": 1709337600,
        },
    ]

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/routes/101/vehicles")
        assert response.status_code == 200
        data = response.json()
        # Should only return vehicles on route 101, not 202
        assert len(data) == 1
        assert data[0]["vehicle_id"] == "BUS-42"
    finally:
        app.dependency_overrides.clear()


@patch("better_transit.routes.routes.get_route_by_id")
def test_route_vehicles_not_found(mock_get_route):
    mock_get_route.return_value = None

    mock_session = AsyncMock()
    app.dependency_overrides[get_session] = _override_session(mock_session)

    try:
        client = TestClient(app)
        response = client.get("/routes/nonexistent/vehicles")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
