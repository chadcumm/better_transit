# Product Requirements Document — Better Transit

## Vision

A personal transit app for Kansas City that provides real-time arrival info, trip planning with customizable routing parameters, and a clean native iOS experience. Built as an alternative to Transit App with full control over the routing engine.

## Target User

Personal use — the developer. Designed for one person's daily transit needs in Kansas City.

## Data Source

KCATA (Kansas City Area Transportation Authority) GTFS feeds:
- **GTFS Static**: Routes, stops, schedules, calendar dates
- **GTFS Realtime**: Vehicle positions, trip updates, service alerts

## Core Features (Priority Order)

### 1. Nearby Stops

Show transit stops near the user's current location with upcoming arrivals.

- Display stops within configurable walking radius
- For each stop: show route(s) serving it and next 3 arrivals
- Use real-time data when available, fall back to scheduled times
- Sort by walking distance

### 2. Real-Time Arrivals

Live arrival predictions for any selected stop.

- Show all routes serving a stop with predicted arrival times
- Indicate whether prediction is real-time or scheduled
- Auto-refresh on a reasonable interval
- Show vehicle positions on route when available

### 3. Custom Trip Planner

Plan a trip with tunable routing parameters. This is the core differentiator.

**Inputs:**
- Origin and destination (coordinates or stop)
- Departure time (now or scheduled)

**Tunable Parameters:**
- Walking distance tolerance: slider from 5 min to 20 min
- Transfer preferences: direct only / 1 transfer / any
- Optimization mode: fastest / least walking / fewest transfers / show all Pareto-optimal

**Output:**
- One or more trip options with legs (walk, ride, transfer)
- Total time, walking time, wait time, number of transfers
- Real-time adjustments when available

### 4. Route Explorer

View a route's full path, schedule, and real-time vehicle positions.

- Route map with stop locations
- Full schedule (timetable view)
- Current vehicle positions along the route
- Service pattern (weekday/weekend/holiday variations)

### 5. Service Alerts

Show active KCATA service alerts.

- Current alerts with affected routes/stops
- Alert severity and time range
- Push notification support (future)

## Non-Goals (v1)

- Multi-agency support (KCATA only)
- Social features
- Fare payment integration
- Android app
- Offline mode
- Accessibility routing (wheelchair, etc.)
