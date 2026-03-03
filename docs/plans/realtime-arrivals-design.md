# Real-Time Arrivals — Design

## Endpoints

- `GET /stops/{stop_id}/arrivals` — arrivals with RT predictions
- `GET /routes/{route_id}/vehicles` — live vehicle positions

## RT Merge Strategy

For each scheduled arrival at a stop:
1. Fetch GTFS-RT TripUpdates feed
2. Build index: `(trip_id, stop_id) -> stop_time_update`
3. For each scheduled departure:
   - If RT update exists for that trip+stop, adjust times by delay and set `is_realtime=true`
   - If no RT update, use scheduled times with `is_realtime=false`

## ArrivalResponse Fields

- `arrival_time` / `departure_time` — predicted time (RT-adjusted if available)
- `scheduled_arrival_time` / `scheduled_departure_time` — always the scheduled time
- `delay_seconds` — seconds of delay from RT (null if no RT data)
- `is_realtime` — whether RT prediction was applied

## Vehicle Positions

- Fetch all positions from GTFS-RT VehiclePositions feed
- Filter to requested route_id
- Return vehicle_id, trip_id, lat/lon, timestamp

## Key Decision

RT feeds are fetched on each request (no caching layer yet). For a personal app with one user, this is fine. A cache/store can be added later if needed.
