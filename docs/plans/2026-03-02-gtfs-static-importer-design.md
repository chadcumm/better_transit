# Design Doc: GTFS Static Importer

**Date:** 2026-03-02
**Status:** Approved

## Summary

Build the GTFS static data import pipeline: download KCATA's GTFS feed, parse CSV files into validated models, and load into PostgreSQL + PostGIS. This is the data foundation every feature depends on.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Parsing approach | Raw CSV + Pydantic models | GTFS CSVs are simple; Pydantic gives validation and model reuse with FastAPI |
| Loading approach | Full replace (truncate + insert) | Personal app, one user — simplicity over zero-downtime |
| Database access | SQLAlchemy + Alembic + GeoAlchemy2 | Industry standard, good async support, handles PostGIS |
| Local database | Docker Compose with PostGIS | Isolated, easy to spin up/tear down |
| Import trigger | CLI command | Useful for dev, easily callable from Lambda later |

## Data Source

- **GTFS Static URL:** `http://www.kc-metro.com/gtf/google_transit.zip`
- **Feed directory:** `http://www.kc-metro.com/gtf/` (has dated archives)
- **Size:** ~2 MB ZIP
- **Update frequency:** Updated by KCATA periodically (weekly to monthly)

## Architecture

### File Structure

```
api/src/better_transit/
├── db.py                    # SQLAlchemy engine/session setup
├── config.py                # Pydantic BaseSettings for env vars
├── gtfs/
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy table models
│   ├── schemas.py           # Pydantic models for GTFS CSV rows
│   ├── downloader.py        # Download + extract GTFS ZIP
│   ├── parser.py            # Read CSVs into Pydantic models
│   ├── loader.py            # Bulk insert into PostgreSQL
│   └── importer.py          # Orchestrator + CLI entry point
docker-compose.yml           # PostGIS container (project root)
```

### New Dependencies

- `sqlalchemy[asyncio]` — async ORM/Core
- `asyncpg` — async PostgreSQL driver
- `alembic` — schema migrations
- `geoalchemy2` — PostGIS support for SQLAlchemy
- `shapely` — geometry objects
- `pydantic-settings` — BaseSettings for config

## Database Schema

### Tables

| Table | GTFS File | Key Columns | PostGIS |
|-------|-----------|-------------|---------|
| `agency` | `agency.txt` | agency_id, name, url, timezone | — |
| `routes` | `routes.txt` | route_id, agency_id, short_name, long_name, type, color | — |
| `stops` | `stops.txt` | stop_id, name, lat, lon, location_type, parent_station | `POINT` geometry |
| `trips` | `trips.txt` | trip_id, route_id, service_id, headsign, direction_id, shape_id | — |
| `stop_times` | `stop_times.txt` | trip_id, stop_id, arrival_time, departure_time, stop_sequence | — |
| `calendar` | `calendar.txt` | service_id, mon-sun booleans, start_date, end_date | — |
| `calendar_dates` | `calendar_dates.txt` | service_id, date, exception_type | — |
| `shapes` | `shapes.txt` | shape_id, lat, lon, sequence, dist_traveled | — |
| `shape_geoms` | (derived) | shape_id, geom | `LINESTRING` (aggregated) |

### Key Indexes

- `stops` — spatial index on geometry column (nearby stops queries)
- `stop_times` — composite on `(stop_id, departure_time)` and `(trip_id, stop_sequence)`
- `trips` — on `(route_id, service_id)`
- `calendar_dates` — on `(service_id, date)`

## Import Pipeline

```
CLI: python -m better_transit.gtfs.importer
  │
  ├── 1. Download google_transit.zip from KCATA URL
  ├── 2. Extract to temp directory
  ├── 3. For each GTFS file:
  │      ├── Read CSV with csv.DictReader
  │      ├── Validate each row into Pydantic schema
  │      └── Collect validated records
  ├── 4. Begin database transaction
  │      ├── Truncate all GTFS tables (in FK-safe order)
  │      ├── Bulk insert all records (executemany)
  │      └── Aggregate shape points into LINESTRING geometries
  ├── 5. Commit transaction
  └── 6. Log summary (rows loaded per table, duration)
```

**Error handling:** Transaction rolls back on failure, existing data untouched. Invalid CSV rows are logged and skipped.

## Configuration

Environment variables (with defaults for local dev):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://better_transit:dev@localhost:5432/better_transit` | PostgreSQL connection string |
| `GTFS_STATIC_URL` | `http://www.kc-metro.com/gtf/google_transit.zip` | KCATA GTFS static feed URL |

Using Pydantic `BaseSettings`, loaded from `.env` file or environment.

## Docker Compose (Local Dev)

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: better_transit
      POSTGRES_USER: better_transit
      POSTGRES_PASSWORD: dev
```

## Testing Strategy

- **Unit tests:** Pydantic schema validation with sample CSV rows (valid + invalid)
- **Integration test:** Download real KCATA feed, parse all files, verify row counts and data integrity
- **Database test:** Load a small fixture into a test PostGIS container, verify queries work
