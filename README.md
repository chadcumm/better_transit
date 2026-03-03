# Better Transit

A personal transit app for Kansas City, built as a better alternative to Transit App.

## What This Is

Backend API and infrastructure for a transit app focused on:
- Real-time arrival info using KCATA GTFS data
- Custom trip planning with tunable routing parameters (walking tolerance, transfer preferences, multi-criteria optimization)
- Clean, fast experience for daily transit use

## Tech Stack

- **Backend:** Python, FastAPI
- **Routing:** Custom RAPTOR algorithm
- **Database:** PostgreSQL + PostGIS
- **Infrastructure:** AWS via SST (serverless)
- **Package manager:** uv
- **Frontend:** Native iOS SwiftUI (separate repo)

## Getting Started

```bash
# Install dependencies
cd api && uv sync

# Run the API locally
cd api && uv run fastapi dev src/better_transit/main.py

# Run tests
cd api && uv run pytest

# Lint
cd api && uv run ruff check .
```

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Decision Records](docs/decisions/)
