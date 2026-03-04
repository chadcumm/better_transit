# Fix Known Issues — Design

**Goal:** Address all open findings from the security audit, devil's advocate review, and pending decisions. Harden the deployed app and update stale documentation.

**Approach:** Single branch (`fix/known-issues`), one commit per logical fix, one deploy at the end.

## High Priority

### D1: Async I/O for RT handlers
Wrap three blocking `fetch_*` calls with `asyncio.to_thread()`:
- `routes/alerts.py` — `fetch_service_alerts()`
- `routes/stops.py` — `fetch_trip_updates()` (two call sites)

No new dependencies. One-line change per call site.

### D4/#38: Route shape/stops direction mismatch
Change route detail endpoint to select a single representative trip, then derive both shape_id and stop list from that trip. Default to `direction_id=0`. Add optional `?direction=0|1` query parameter.

Files: `routes/routes.py`, `gtfs/queries.py`

### ARCHITECTURE.md update
- "Aurora Serverless" → "Neon PostgreSQL (serverless)"
- SST resources section: note `sst.config.ts` at repo root
- Remove references to `infra/` directory

## Medium Priority

### M3/M5: Download size limit
Replace `shutil.copyfileobj` with chunked read loop tracking bytes. Abort if > 100 MB (`MAX_DOWNLOAD_SIZE`).

### M4: Zip bomb protection
Check total uncompressed size from ZipInfo before extraction. Reject if > 500 MB or compression ratio > 100:1.

### M1: f-string TRUNCATE hardening
Add explicit validation that `table_name` is in `TRUNCATE_ORDER` before executing the TRUNCATE statement.

### M2: String length limits
Add `max_length` to Pydantic schema fields (stop_name, route_long_name, trip_headsign, etc.). Generous limits (500-1000 chars). No SQL column changes.

## RAPTOR Caching (D3)

Module-level cache dict in `routing/builder.py`, keyed by service date. 5-minute TTL. Cold starts rebuild from DB. Warm Lambda invocations reuse cached data. KCATA data fits comfortably in the 512 MB Lambda memory.

## Low Priority & Documentation

### D2/#19: Overnight service_id gap
Add code comment documenting the midnight-5AM limitation. No code change.

### #4: Single transaction scope
Add code comment documenting the trade-off. No code change (cron runs at 6 AM CT, no traffic).

### #5: TRUNCATE CASCADE
Remove `CASCADE` — no FKs exist, CASCADE is a no-op landmine.

### L1: Dev credentials
Add comments noting dev-only defaults in `docker-compose.yml` and `config.py`.

### Clean up review artifacts
Move `REVIEW_NOTES.md`, `SECURITY_AUDIT.md`, `DECISIONS_PENDING.md` to `docs/` or remove after fixes are deployed.
