# Nearby Stops — Design

## Endpoint

`GET /stops/nearby?lat={lat}&lon={lon}&radius={radius_m}&limit={limit}`

## Key Decisions

- **Spatial query**: PostGIS `ST_DWithin` with Geography cast for accurate meter-based distance calculation. Uses the existing GiST index on `stops.geom`.
- **Service resolution**: `get_active_service_ids(date)` combines `calendar` table (regular weekday patterns within date range) with `calendar_dates` exceptions (type 1 = add, type 2 = remove).
- **Arrivals**: For each nearby stop, return next 3 departures from `stop_times` joined with `trips` for route/headsign info. Filtered to active services and times after "now".
- **Routes**: Each stop includes the distinct routes serving it, resolved via `stop_times -> trips -> routes`.
- **Real-time**: Returns `is_realtime: false` for all arrivals. Phase 6 will overlay GTFS-RT trip updates.
- **Defaults**: radius=800m, limit=20 stops, 3 arrivals per stop.

## Response Shape

```json
[
  {
    "stop_id": "1161406",
    "stop_name": "ON N 110TH ST AT VILLAGE WEST APTS SB",
    "stop_lat": 39.127334,
    "stop_lon": -94.835239,
    "distance_meters": 150.0,
    "routes": [
      {"route_id": "101", "route_short_name": "101", "route_long_name": "State"}
    ],
    "next_arrivals": [
      {
        "trip_id": "T1",
        "route_id": "101",
        "headsign": "Downtown",
        "arrival_time": "08:00:00",
        "departure_time": "08:01:00",
        "is_realtime": false
      }
    ]
  }
]
```
