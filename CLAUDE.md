# CLAUDE.md

## Project Overview

Better Transit is a personal transit app for Kansas City using KCATA (Kansas City Area Transportation Authority) GTFS data. The backend is Python + FastAPI with a custom RAPTOR routing engine. The iOS frontend (SwiftUI) lives in a separate repo.

**Tech stack:** Python, FastAPI, PostgreSQL + PostGIS, AWS (via SST), uv

**Key docs:**
- `docs/PRD.md` — product requirements
- `docs/ARCHITECTURE.md` — system architecture
- `docs/decisions/` — architectural decision records
- `docs/plans/` — feature design documents

## Development Governance

### Planning Before Coding

- **All new features require a design doc** in `docs/plans/` before implementation. Use the brainstorming skill to explore requirements and design before writing code.
- **PRD.md is the source of truth** for what features exist. Don't build features not in the PRD — update the PRD first if something new is needed.
- **ARCHITECTURE.md must be updated** when changing system boundaries, data flow, or tech stack components.
- **ADRs are required** in `docs/decisions/` for significant technical decisions (new dependencies, algorithm choices, infrastructure changes). Use the format in `0001-custom-routing-engine.md` as a template.
- **All design docs need user approval** before implementation begins.

### Code Standards

- **Python backend:** FastAPI, Pydantic v2, async where appropriate
- **Package management:** uv (not pip, not poetry)
- **GTFS data access:** through the `gtfs/` module — no raw GTFS SQL queries in route handlers or other modules
- **Tests required** for the routing engine and all API endpoints
- **Linting:** ruff

### Infrastructure Rules

- All AWS resources defined in SST config — no manual console changes
- Database migrations tracked in version control

## Build & Run Commands

```bash
# API development
cd api && uv run fastapi dev src/better_transit/main.py   # run API locally
cd api && uv run pytest                                     # run tests
cd api && uv run ruff check .                               # lint

# Infrastructure
cd infra && npx sst dev                                     # run SST dev mode
```

## Project Structure

```
better_transit/
├── api/                    # Python backend (FastAPI)
│   ├── pyproject.toml
│   ├── src/better_transit/
│   │   ├── main.py         # FastAPI app entry
│   │   ├── routes/         # API endpoint definitions
│   │   ├── models/         # Pydantic request/response models
│   │   ├── gtfs/           # GTFS static data import & access
│   │   ├── routing/        # RAPTOR trip planning engine
│   │   └── realtime/       # GTFS-RT feed client
│   └── tests/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── decisions/          # ADRs
│   └── plans/              # Feature design docs
└── infra/                  # SST infrastructure config
```
