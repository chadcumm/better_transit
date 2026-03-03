# Design Doc: Project Foundation & Development Governance

**Date:** 2026-03-02
**Status:** Implemented

## Summary

Establish the project foundation for Better Transit: directory scaffolding, governance documents, development rules, and a minimal API skeleton. No application logic — just the structure to build on.

## Decisions Made

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Frontend | Native iOS SwiftUI (separate repo) | Best UX for personal use, not in scope for this repo |
| Backend | Python + FastAPI | Async-friendly, excellent for APIs, good GTFS library ecosystem |
| Routing engine | Custom RAPTOR in Python | Full control over parameters (see ADR-0001) |
| Infrastructure | AWS via SST | Serverless, pay-per-use, minimal ops burden |
| Database | PostgreSQL + PostGIS | Spatial queries for nearby stops, mature GTFS data model |
| Package manager | uv | Fast, modern Python package management |
| Data source | KCATA GTFS Static + Realtime | Only KC transit agency needed for v1 |

## What Was Created

### Governance Documents
- `docs/PRD.md` — Product requirements with prioritized feature list
- `docs/ARCHITECTURE.md` — System architecture, components, data flow, API endpoints
- `docs/decisions/0001-custom-routing-engine.md` — ADR for RAPTOR vs. OTP decision

### Project Rules
- `CLAUDE.md` — Development governance rules ensuring future sessions plan before coding
- All new features require a design doc before implementation
- PRD.md is the source of truth for features
- ADRs required for significant technical decisions

### API Skeleton
- `api/pyproject.toml` — uv project with FastAPI, Pydantic, pytest, ruff
- `api/src/better_transit/main.py` — Minimal FastAPI app with health endpoint
- Module directories: `routes/`, `models/`, `gtfs/`, `routing/`, `realtime/`

### Infrastructure
- `infra/` — Placeholder for SST configuration

## Next Steps

1. Set up SST with basic Lambda + API Gateway
2. Implement GTFS static importer
3. Build nearby stops endpoint
4. Implement RAPTOR routing engine
5. Add real-time data integration
