# Architecture — Better Transit

## System Overview

```
┌─────────────┐         ┌──────────────────────────────────────────┐
│  iOS App     │         │  AWS (via SST)                           │
│  (SwiftUI)   │◄───────►│                                          │
│  separate    │  REST   │  ┌──────────────┐   ┌────────────────┐  │
│  repo        │  API    │  │  API Gateway  │──►│  Lambda         │  │
└─────────────┘         │  └──────────────┘   │  (FastAPI)      │  │
                        │                      │                 │  │
                        │                      │  ┌───────────┐  │  │
                        │                      │  │ Routes    │  │  │
                        │                      │  │ Stops     │  │  │
                        │                      │  │ Trips     │  │  │
                        │                      │  │ Routing   │  │  │
                        │                      │  │ Alerts    │  │  │
                        │                      │  └───────────┘  │  │
                        │                      └────────┬────────┘  │
                        │                               │           │
                        │                      ┌────────▼────────┐  │
                        │                      │  PostgreSQL     │  │
                        │                      │  + PostGIS      │  │
                        │                      │  (Neon          │  │
                        │                      │   Serverless)   │  │
                        │                      └─────────────────┘  │
                        │                                           │
                        │  ┌─────────────────────────────────────┐  │
                        │  │  Scheduled Lambdas                  │  │
                        │  │  - GTFS static import (daily)       │  │
                        │  │  - GTFS-RT fetch (every 30s)        │  │
                        │  └─────────────────────────────────────┘  │
                        └──────────────────────────────────────────┘

                        ┌──────────────────┐
                        │  KCATA GTFS      │
                        │  Static + RT     │
                        │  feeds           │
                        └──────────────────┘
```

## Components

### FastAPI Backend (`api/`)

The main application server, deployed as an AWS Lambda function via SST.

**Modules:**

| Module | Path | Responsibility |
|--------|------|---------------|
| Routes | `routes/` | API endpoint definitions |
| Models | `models/` | Pydantic models for request/response schemas |
| GTFS | `gtfs/` | GTFS static data import, parsing, and database access |
| Routing | `routing/` | RAPTOR trip planning algorithm |
| Realtime | `realtime/` | GTFS-RT feed client and real-time data integration |

### RAPTOR Routing Engine (`routing/`)

Custom implementation of the RAPTOR (Round-bAsed Public Transit Optimized Router) algorithm.

**Why custom:** Full control over routing parameters. OTP is a black box — we need tunable walking tolerance, transfer penalties, and multi-criteria optimization. See [ADR-0001](decisions/0001-custom-routing-engine.md).

**Key capabilities:**
- Round-based algorithm for efficient multi-transfer route finding
- Configurable walking distance tolerance
- Transfer penalty tuning
- Pareto-optimal result set (time vs. transfers vs. walking)
- Integration with real-time trip updates for adjusted predictions

### GTFS Importer (`gtfs/`)

Handles downloading, parsing, and loading KCATA GTFS static data into PostgreSQL.

**Pipeline:**
1. Download GTFS ZIP from KCATA feed URL
2. Parse CSV files (routes, stops, stop_times, trips, calendar, calendar_dates, shapes)
3. Load into PostgreSQL with PostGIS geometry columns for spatial queries
4. Build indexes for routing engine (stop-to-stop connections, transfer points)

**Schedule:** Daily via scheduled Lambda (GTFS static data changes infrequently).

### GTFS-RT Client (`realtime/`)

Fetches and processes GTFS Realtime protobuf feeds.

**Feed types:**
- **Vehicle Positions**: Current location of buses
- **Trip Updates**: Arrival/departure predictions per stop
- **Service Alerts**: Disruptions, detours, cancellations

**Schedule:** Every 30 seconds via scheduled Lambda, writing to a fast-access store (database or cache).

### PostgreSQL + PostGIS

Primary data store for all GTFS data and application state.

**Key tables (conceptual):**
- `routes` — transit routes
- `stops` — stop locations (PostGIS POINT geometry)
- `trips` — individual trips on a route
- `stop_times` — scheduled times at each stop for each trip
- `calendar` / `calendar_dates` — service patterns
- `shapes` — route geometries (PostGIS LINESTRING)
- `realtime_trip_updates` — latest real-time predictions
- `realtime_vehicle_positions` — latest vehicle locations
- `service_alerts` — active alerts

### Infrastructure (SST)

All AWS resources managed via SST (Serverless Stack Toolkit). SST configuration is defined in `sst.config.ts` at the repository root.

**Resources:**
- **API Gateway** — HTTP API fronting the Lambda
- **Lambda** — FastAPI app via Mangum adapter
- **Neon PostgreSQL** — Serverless PostgreSQL + PostGIS
- **Scheduled Lambdas** — GTFS import and RT fetch on cron
- **S3** — GTFS static file storage (optional, for archive)

## Data Flow

### Trip Planning Request

```
iOS App                    API Gateway       Lambda (FastAPI)      PostgreSQL
  │                           │                    │                   │
  │  POST /trips/plan         │                    │                   │
  │  {origin, dest, params}   │                    │                   │
  │──────────────────────────►│───────────────────►│                   │
  │                           │                    │  query stops,     │
  │                           │                    │  stop_times,      │
  │                           │                    │  transfers        │
  │                           │                    │──────────────────►│
  │                           │                    │◄──────────────────│
  │                           │                    │                   │
  │                           │                    │  RAPTOR algorithm  │
  │                           │                    │  (in-memory)       │
  │                           │                    │                   │
  │                           │                    │  apply RT updates  │
  │                           │                    │──────────────────►│
  │                           │                    │◄──────────────────│
  │                           │                    │                   │
  │  [{legs, time, walks...}] │                    │                   │
  │◄──────────────────────────│◄───────────────────│                   │
```

### GTFS Static Import

```
Scheduled Lambda          KCATA GTFS URL         PostgreSQL
  │                           │                      │
  │  download ZIP             │                      │
  │──────────────────────────►│                      │
  │◄──────────────────────────│                      │
  │                           │                      │
  │  parse CSVs                                      │
  │  transform to models                             │
  │                                                  │
  │  UPSERT stops, routes, trips, stop_times...      │
  │─────────────────────────────────────────────────►│
  │                                                  │
  │  rebuild routing indexes                         │
  │─────────────────────────────────────────────────►│
```

## API Endpoints (Planned)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stops/nearby` | Stops near a location with next arrivals |
| GET | `/stops/{stop_id}/arrivals` | Real-time arrivals at a stop |
| POST | `/trips/plan` | Plan a trip with routing parameters |
| GET | `/routes` | List all routes |
| GET | `/routes/{route_id}` | Route details with shape and schedule |
| GET | `/routes/{route_id}/vehicles` | Current vehicle positions |
| GET | `/alerts` | Active service alerts |
| GET | `/health` | Health check |

## iOS App Integration

The iOS app (separate repo, SwiftUI) communicates with the backend via REST API. The API contract is defined by the Pydantic models in `models/`. The app handles:
- Location services
- Map rendering (MapKit)
- Local caching of route/stop data
- Push notifications (via APNs, future)
