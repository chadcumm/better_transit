"""Tests for GTFS-RT client with mock protobuf data."""

from unittest.mock import patch

import pytest
from google.transit import gtfs_realtime_pb2

from better_transit.realtime.client import (
    _parse_alert,
    _parse_trip_update,
    _parse_vehicle_position,
    fetch_service_alerts,
    fetch_trip_updates,
    fetch_vehicle_positions,
)


def _make_alert_feed() -> gtfs_realtime_pb2.FeedMessage:
    """Create a sample GTFS-RT feed with a service alert."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1709337600

    entity = feed.entity.add()
    entity.id = "alert-1"
    alert = entity.alert

    header = alert.header_text.translation.add()
    header.text = "Route 101 Detour"
    header.language = "en"

    desc = alert.description_text.translation.add()
    desc.text = "Route 101 is detoured due to construction"
    desc.language = "en"

    informed = alert.informed_entity.add()
    informed.route_id = "101"

    period = alert.active_period.add()
    period.start = 1709337600
    period.end = 1709424000

    return feed


def _make_trip_update_feed() -> gtfs_realtime_pb2.FeedMessage:
    """Create a sample GTFS-RT feed with a trip update."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1709337600

    entity = feed.entity.add()
    entity.id = "tu-1"
    tu = entity.trip_update
    tu.trip.trip_id = "T1"
    tu.trip.route_id = "101"

    stu = tu.stop_time_update.add()
    stu.stop_id = "S1"
    stu.stop_sequence = 1
    stu.arrival.delay = 120
    stu.departure.delay = 130

    return feed


def _make_vehicle_position_feed() -> gtfs_realtime_pb2.FeedMessage:
    """Create a sample GTFS-RT feed with a vehicle position."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    feed.header.timestamp = 1709337600

    entity = feed.entity.add()
    entity.id = "vp-1"
    vp = entity.vehicle
    vp.vehicle.id = "BUS-42"
    vp.trip.trip_id = "T1"
    vp.trip.route_id = "101"
    vp.position.latitude = 39.1
    vp.position.longitude = -94.5
    vp.timestamp = 1709337600

    return feed


# --- Alert parsing ---


def test_parse_alert():
    feed = _make_alert_feed()
    entity = feed.entity[0]
    result = _parse_alert(entity)

    assert result["alert_id"] == "alert-1"
    assert result["header"] == "Route 101 Detour"
    assert result["description"] == "Route 101 is detoured due to construction"
    assert result["affected_route_ids"] == ["101"]
    assert "2024-03-01" in result["start_time"]
    assert "2024-03-02" in result["end_time"]
    # Verify ISO 8601 format with timezone offset
    assert result["start_time"].endswith("-06:00") or result["start_time"].endswith("-05:00")
    assert result["end_time"].endswith("-06:00") or result["end_time"].endswith("-05:00")


@patch("better_transit.realtime.client._fetch_feed")
def test_fetch_service_alerts(mock_fetch):
    mock_fetch.return_value = _make_alert_feed()

    alerts = fetch_service_alerts()
    assert len(alerts) == 1
    assert alerts[0]["header"] == "Route 101 Detour"


@patch("better_transit.realtime.client._fetch_feed")
def test_fetch_service_alerts_handles_error(mock_fetch):
    mock_fetch.side_effect = Exception("Network error")

    alerts = fetch_service_alerts()
    assert alerts == []


# --- Trip update parsing ---


def test_parse_trip_update():
    feed = _make_trip_update_feed()
    entity = feed.entity[0]
    result = _parse_trip_update(entity)

    assert result["trip_id"] == "T1"
    assert result["route_id"] == "101"
    assert len(result["stop_time_updates"]) == 1
    assert result["stop_time_updates"][0]["arrival_delay"] == 120
    assert result["stop_time_updates"][0]["departure_delay"] == 130


@patch("better_transit.realtime.client._fetch_feed")
def test_fetch_trip_updates(mock_fetch):
    mock_fetch.return_value = _make_trip_update_feed()

    updates = fetch_trip_updates()
    assert len(updates) == 1
    assert updates[0]["trip_id"] == "T1"


# --- Vehicle position parsing ---


def test_parse_vehicle_position():
    feed = _make_vehicle_position_feed()
    entity = feed.entity[0]
    result = _parse_vehicle_position(entity)

    assert result["vehicle_id"] == "BUS-42"
    assert result["trip_id"] == "T1"
    assert result["latitude"] == pytest.approx(39.1, abs=1e-4)
    assert result["longitude"] == pytest.approx(-94.5, abs=1e-4)


@patch("better_transit.realtime.client._fetch_feed")
def test_fetch_vehicle_positions(mock_fetch):
    mock_fetch.return_value = _make_vehicle_position_feed()

    positions = fetch_vehicle_positions()
    assert len(positions) == 1
    assert positions[0]["vehicle_id"] == "BUS-42"


# --- Alerts API endpoint ---


@patch("better_transit.routes.alerts.fetch_service_alerts")
def test_alerts_endpoint(mock_fetch_alerts):
    from fastapi.testclient import TestClient

    from better_transit.main import app

    mock_fetch_alerts.return_value = [
        {
            "alert_id": "alert-1",
            "header": "Route 101 Detour",
            "description": "Detour due to construction",
            "severity": "WARNING",
            "affected_route_ids": ["101"],
            "affected_stop_ids": [],
            "start_time": "1709337600",
            "end_time": "1709424000",
        }
    ]

    client = TestClient(app)
    response = client.get("/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["alert_id"] == "alert-1"
    assert data[0]["header"] == "Route 101 Detour"
