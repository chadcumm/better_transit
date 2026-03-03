# Route Explorer — Design

## Endpoints

- `GET /routes` — list all routes with basic info
- `GET /routes/{route_id}` — route detail with shape geometry and stop schedule

## Key Decisions

- **Shape geometry**: Stored as PostGIS LINESTRING in `shape_geoms` table. Converted to GeoJSON via `ST_AsGeoJSON` for the API response. The shape_id is resolved from the route's trips.
- **Stop schedule**: Returns the ordered stops from a representative trip on the route (for currently active services). Each stop includes arrival/departure times and coordinates.
- **Service resolution**: Same `get_active_service_ids(date)` used by nearby stops.
- **Vehicle positions**: Deferred to Phase 6 (GTFS-RT integration).
- **Timetable view**: Currently returns one representative trip's schedule. Full multi-trip timetable can be added later if needed.

## Response Shape (route detail)

```json
{
  "route_id": "101",
  "agency_id": "KCATA",
  "route_short_name": "101",
  "route_long_name": "State",
  "route_type": 3,
  "route_color": "FF0000",
  "shape_geojson": {"type": "LineString", "coordinates": [...]},
  "stops": [
    {
      "stop_id": "1",
      "stop_name": "First St",
      "stop_lat": 39.09,
      "stop_lon": -94.57,
      "stop_sequence": 1,
      "arrival_time": "08:00:00",
      "departure_time": "08:01:00"
    }
  ]
}
```
