# Decisions Pending Owner Review

Items identified during the build session that need the project owner's input before the next development cycle.

---

## Decided by Proxy (Low-Risk, Reversible)

### D1. Blocking I/O in async handlers (R11/R13)

**Context:** The GTFS-RT client (`realtime/client.py`) uses synchronous `urllib.request.urlopen` for HTTP fetches. These blocking calls are made inside `async def` route handlers in three places:

- `routes/alerts.py:12` -- `fetch_service_alerts()`
- `routes/stops.py:97` -- `fetch_trip_updates()` in `nearby_stops`
- `routes/stops.py:177` -- `fetch_trip_updates()` in `stop_arrivals`

Each call blocks the asyncio event loop for up to 15 seconds (the fetch timeout). No other requests can be served during that time.

**Options:**
- (a) Wrap calls with `await asyncio.to_thread(fetch_service_alerts)` -- minimal change, runs blocking call in thread pool
- (b) Rewrite RT client with `httpx.AsyncClient` -- more correct, adds a dependency
- (c) Change handlers from `async def` to `def` -- FastAPI auto-runs sync handlers in a thread pool

**Decision: Option (a) -- `asyncio.to_thread`**

**Rationale:** Smallest change, no new dependencies, solves the event loop blocking. The handlers must stay `async def` because they also `await` DB queries. Option (b) is technically better but adds `httpx` as a dependency for three call sites -- not worth it for a single-user app. Can upgrade to httpx later if the RT client grows.

**Implementation:** Change each call site from:
```python
alerts = fetch_service_alerts()
```
to:
```python
import asyncio
alerts = await asyncio.to_thread(fetch_service_alerts)
```

---

### D2. Overnight service_id resolution gap (#19)

**Context:** GTFS allows departure times exceeding 24:00:00 for overnight service. A departure at `"25:30:00"` means 1:30 AM the next day, but belongs to the previous day's service_id.

Between midnight and ~5 AM, the app resolves service_ids for today (Tuesday), but overnight trips belong to yesterday's service (Monday). Those trips are invisible to the arrivals query.

**Assessment:**
- KCATA has minimal overnight service -- a few routes run until ~1 AM
- The time conversion is correct (25:30 -> next day 1:30 AM, per ADR-0002)
- Only the service_id resolution is affected, in a narrow time window
- The proper fix requires resolving both today's and yesterday's service_ids for early-morning queries, then filtering appropriately. This adds meaningful complexity.

**Decision: Accept as known limitation. Document, do not fix now.**

**Rationale:** This is a well-known hard problem in GTFS implementations. The fix adds complexity disproportionate to the impact (a few routes, midnight-5AM window, single user). The correct fix is to also resolve yesterday's services during early morning hours and query for times >= current_time on today's services PLUS times >= (current_time + 24*3600) on yesterday's services. This is worth doing when the app is in daily use and the gap is actually noticed.

**Action:** Add a code comment at the service_id resolution point documenting the limitation.

---

## Deferred to Owner (Higher-Risk or Architectural)

### D3. RAPTOR data caching (I10)

**Context:** Every `POST /trips/plan` request calls `build_raptor_data()` (`routes/trips.py:52`), which runs full DB queries to build the in-memory RAPTOR data structures (routes, trips, stop_times, transfers). For KCATA (~3K trips, 187K stop_times), this could take several seconds per request.

**Options:**
- (a) **No caching** -- rebuild every request. Simplest. Correct. Slow.
- (b) **In-memory cache by service date with TTL** -- e.g., `@lru_cache` or a module-level dict keyed by `today`. Invalidate at midnight or after GTFS import.
- (c) **Pre-build on startup + GTFS import trigger** -- build once, rebuild when data changes.

**Recommendation: Option (b) -- cache by service date with short TTL (~5 min)**

A simple dict check (`if cached_date == today and age < 300: return cached_data`) would eliminate redundant DB work. The data only changes when a new GTFS import runs (at most daily). For a single-user app, even a naive cache eliminates 99% of rebuild overhead.

However, this is an **architectural decision** about where state lives in the app. The caching strategy affects:
- Memory footprint (RAPTOR data for KCATA is ~tens of MB)
- Correctness after GTFS reimport (stale cache risk)
- Serverless deployment (Lambda cold starts would still rebuild)

**Owner input needed:** Is this worth doing now, or is per-request rebuild acceptable for MVP? The answer depends on whether trip planning latency matters at this stage.

---

### D4. Shape/stops direction mismatch in route explorer (#38)

**Context:** The route detail endpoint (`routes/routes.py:57-70`) makes two independent queries:
- `get_shape_id_for_route()` -- picks an arbitrary trip's shape_id (LIMIT 1, no ORDER BY)
- `get_stops_for_route()` -- picks an arbitrary trip's stop list (LIMIT 1, no ORDER BY)

Because there's no ORDER BY or direction filter, PostgreSQL can return a shape from direction 0 (outbound) and stops from direction 1 (inbound). The map would show the outbound route line, but the stop list would show inbound stops -- they won't align geographically.

**Fix options:**
- (a) **Single representative trip** -- select one trip, use its shape_id AND its stop list. Both are guaranteed consistent.
- (b) **Filter by direction_id** -- pass `direction_id=0` to both queries. Returns one direction consistently but ignores the other.
- (c) **Return both directions** -- the API returns stops and shapes for each direction separately. Most complete but changes the response model.

**Recommendation: Option (a) for MVP, evolve to (c) later**

Option (a) is the minimal correct fix -- select a representative trip once, derive both shape and stops from it. This guarantees consistency. The iOS app can add a direction toggle later (calling with `?direction=0` or `?direction=1`).

**Owner input needed:** This changes the route detail query pattern and response semantics. Should the MVP show one direction (which one -- outbound by default?) or both? Does the iOS UI have a direction concept yet?

---

*Generated: 2026-03-02*
*Session: better-transit-build*
