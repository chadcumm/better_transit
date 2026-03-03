"""GTFS-RT client — fetches and parses GTFS Realtime protobuf feeds."""

import logging
import urllib.request
from typing import Any
from urllib.parse import urlparse

from google.transit import gtfs_realtime_pb2

from better_transit.config import settings

logger = logging.getLogger(__name__)

FETCH_TIMEOUT = 15
MAX_FEED_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_SCHEMES = {"http", "https"}


def _fetch_feed(url: str) -> gtfs_realtime_pb2.FeedMessage:
    """Fetch a GTFS-RT protobuf feed from a URL."""
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme '{parsed.scheme}' is not allowed. Use http:// or https://"
        )

    headers = {}
    if settings.gtfs_rt_api_key:
        headers["Authorization"] = f"Bearer {settings.gtfs_rt_api_key}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as response:
        data = response.read(MAX_FEED_SIZE + 1)
        if len(data) > MAX_FEED_SIZE:
            raise ValueError(f"Feed exceeds {MAX_FEED_SIZE} byte size limit")

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(data)
    return feed


def fetch_service_alerts() -> list[dict[str, Any]]:
    """Fetch and parse service alerts from the GTFS-RT feed."""
    url = settings.gtfs_rt_service_alerts_url
    if not url:
        return []

    try:
        feed = _fetch_feed(url)
    except Exception:
        logger.exception("Failed to fetch service alerts from %s", url)
        return []

    return [_parse_alert(entity) for entity in feed.entity if entity.HasField("alert")]


def fetch_trip_updates() -> list[dict[str, Any]]:
    """Fetch and parse trip updates from the GTFS-RT feed."""
    url = settings.gtfs_rt_trip_updates_url
    if not url:
        return []

    try:
        feed = _fetch_feed(url)
    except Exception:
        logger.exception("Failed to fetch trip updates from %s", url)
        return []

    return [
        _parse_trip_update(entity)
        for entity in feed.entity
        if entity.HasField("trip_update")
    ]


def fetch_vehicle_positions() -> list[dict[str, Any]]:
    """Fetch and parse vehicle positions from the GTFS-RT feed."""
    url = settings.gtfs_rt_vehicle_positions_url
    if not url:
        return []

    try:
        feed = _fetch_feed(url)
    except Exception:
        logger.exception("Failed to fetch vehicle positions from %s", url)
        return []

    return [
        _parse_vehicle_position(entity)
        for entity in feed.entity
        if entity.HasField("vehicle")
    ]


def _parse_alert(entity: gtfs_realtime_pb2.FeedEntity) -> dict[str, Any]:
    """Parse a single FeedEntity with an alert into a dict."""
    alert = entity.alert

    header = ""
    if alert.header_text.translation:
        header = alert.header_text.translation[0].text

    description = None
    if alert.description_text.translation:
        description = alert.description_text.translation[0].text

    affected_route_ids = []
    affected_stop_ids = []
    for informed in alert.informed_entity:
        if informed.route_id:
            affected_route_ids.append(informed.route_id)
        if informed.stop_id:
            affected_stop_ids.append(informed.stop_id)

    severity = None
    if alert.severity_level:
        severity_map = {
            1: "UNKNOWN",
            2: "INFO",
            3: "WARNING",
            4: "SEVERE",
        }
        severity = severity_map.get(alert.severity_level)

    start_time = None
    end_time = None
    if alert.active_period:
        from datetime import datetime

        from better_transit.gtfs.time_utils import KANSAS_CITY_TZ

        period = alert.active_period[0]
        if period.start:
            start_time = datetime.fromtimestamp(
                period.start, tz=KANSAS_CITY_TZ
            ).isoformat()
        if period.end:
            end_time = datetime.fromtimestamp(
                period.end, tz=KANSAS_CITY_TZ
            ).isoformat()

    return {
        "alert_id": entity.id,
        "header": header,
        "description": description,
        "severity": severity,
        "affected_route_ids": affected_route_ids,
        "affected_stop_ids": affected_stop_ids,
        "start_time": start_time,
        "end_time": end_time,
    }


def _parse_trip_update(entity: gtfs_realtime_pb2.FeedEntity) -> dict[str, Any]:
    """Parse a single FeedEntity with a trip_update into a dict."""
    tu = entity.trip_update
    stop_time_updates = []
    for stu in tu.stop_time_update:
        stop_time_updates.append({
            "stop_id": stu.stop_id,
            "stop_sequence": stu.stop_sequence,
            "arrival_delay": stu.arrival.delay if stu.HasField("arrival") else None,
            "departure_delay": (
                stu.departure.delay if stu.HasField("departure") else None
            ),
        })

    return {
        "trip_id": tu.trip.trip_id,
        "route_id": tu.trip.route_id,
        "stop_time_updates": stop_time_updates,
    }


def _parse_vehicle_position(entity: gtfs_realtime_pb2.FeedEntity) -> dict[str, Any]:
    """Parse a single FeedEntity with a vehicle position into a dict."""
    vp = entity.vehicle
    return {
        "vehicle_id": vp.vehicle.id if vp.vehicle.id else entity.id,
        "trip_id": vp.trip.trip_id if vp.HasField("trip") else None,
        "route_id": vp.trip.route_id if vp.HasField("trip") else None,
        "latitude": vp.position.latitude if vp.HasField("position") else None,
        "longitude": vp.position.longitude if vp.HasField("position") else None,
        "timestamp": vp.timestamp if vp.timestamp else None,
    }
