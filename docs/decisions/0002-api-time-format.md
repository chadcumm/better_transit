# ADR-0002: API Time Format — Local Time with Timezone Offset

**Date:** 2026-03-02
**Status:** Accepted

## Context

GTFS times are stored as local-time strings (e.g., `"14:30:00"` in America/Chicago). The API needs to return properly formatted datetimes that the iOS app can parse reliably.

Two options were considered:

- **Option A: UTC** — e.g., `"2026-03-02T20:30:00Z"`
- **Option B: Local time with offset** — e.g., `"2026-03-02T14:30:00-06:00"`

Both are ISO 8601 compliant. This decision is low-risk and reversible (changing serialization format does not affect the data model).

## Decision

**Return local time with timezone offset (Option B).**

API responses use ISO 8601 with explicit offset: `"2026-03-02T14:30:00-06:00"`.

## Rationale

1. **GTFS data is local time.** Converting to UTC on the server only to have the client convert back adds complexity with no benefit.
2. **Matches the user's mental model.** Bus schedules say "2:30 PM" in local time. The API should reflect that directly.
3. **Unambiguous.** The offset (`-06:00` CST / `-05:00` CDT) tells the client exactly what timezone applies. Swift's `ISO8601DateFormatter` handles this natively.
4. **Single-city, single-user app.** The main argument for UTC is multi-timezone consumers, which does not apply here.
5. **Simpler server logic.** No need to resolve GTFS agency timezone and perform UTC conversion for every time value.

## Consequences

**Positive:**
- Simpler server implementation — format GTFS time + date + known offset
- API responses match printed bus schedules
- iOS client can display times directly or convert as needed

**Negative:**
- If the app ever supports multiple cities in different timezones, consumers would need to handle mixed offsets. Mitigation: this is a single-city personal app; can revisit if scope changes.

**Implementation notes:**
- The server must know the current UTC offset for America/Chicago (CST = -06:00, CDT = -05:00) to attach the correct offset based on the date.
- GTFS times exceeding 24:00:00 (overnight service) must be resolved to the correct calendar date before formatting.
