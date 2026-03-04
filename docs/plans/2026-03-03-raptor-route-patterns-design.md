# Fix RAPTOR Route Patterns — Design

**Goal:** Stop silently dropping express and short-turn trips from the RAPTOR routing engine by grouping trips into route patterns based on their actual stop sequences.

**Approach:** Group trips by their unique stop pattern (ordered tuple of stop_ids) instead of by GTFS route_id alone. Each unique pattern becomes a separate `TransitRoute` in the RAPTOR data structures.

## The Problem

In `builder.py`, the first trip on a GTFS route defines the "canonical" stop list. In `raptor.py:131`, any trip whose stop count doesn't match is silently skipped. This drops express trips (which skip stops) and short-turn trips (which cover a subset of the route).

KCATA has routes with express variants (e.g., MAX). These trips are invisible to the trip planner.

## The Fix

### builder.py — Group by stop pattern

After grouping trips by `route_id`, further group by stop pattern:

1. For each GTFS route_id, collect all trips and their stop sequences
2. Group trips whose stop_id tuples are identical into "patterns"
3. Each pattern becomes its own `TransitRoute` with a synthetic ID: `{route_id}_p{index}`
4. Index 0 goes to the most common pattern (typically the full local run)
5. The `stop_routes` index maps each stop_id to all pattern IDs it appears in

### raptor.py — Remove the guard

The `if len(trip.stop_times) != num_stops: continue` guard is no longer needed since every trip in a pattern has the same stops by construction. Remove it.

### routes/trips.py — Strip pattern suffix

When building the trip plan response, strip the `_pN` suffix from route_id to recover the original GTFS route_id for display. The pattern ID is an internal detail.

## What doesn't change

- `TransitRoute`, `RaptorData`, `TripSchedule`, `StopTime` data structures
- The RAPTOR algorithm itself (rounds, scanning, transfers)
- API response models
- No new dependencies
