# ADR-0001: Custom RAPTOR Routing Engine

**Date:** 2026-03-02
**Status:** Accepted

## Context

Better Transit needs a trip planning engine that supports customizable routing parameters: walking distance tolerance, transfer preferences, and multi-criteria optimization (fastest vs. least walking vs. fewest transfers).

The main alternative is OpenTripPlanner (OTP), a mature open-source routing engine used by many transit agencies.

## Options Considered

### Option A: OpenTripPlanner (OTP)

- Mature, well-tested routing engine
- Supports GTFS out of the box
- Java-based, would need to run as a separate service
- Routing parameters are limited and hard to customize
- Black box for multi-criteria optimization — can't easily expose Pareto-optimal trade-offs to the user
- Heavy resource footprint for a single-city personal app

### Option B: Custom RAPTOR Implementation in Python

- RAPTOR (Round-bAsed Public Transit Optimized Router) is a well-documented algorithm with published papers
- Full control over routing parameters and optimization criteria
- Can expose Pareto-optimal result sets (time vs. transfers vs. walking)
- Runs in-process with the FastAPI app — no separate service to manage
- More development effort upfront
- Python performance is sufficient for single-city, single-user workloads

## Decision

**Build a custom RAPTOR routing engine in Python.**

The core value proposition of Better Transit is customizable routing. Using OTP would mean fighting against its abstractions to expose the parameters we need. RAPTOR is well-documented in academic literature and straightforward to implement for a single-agency dataset.

## Consequences

**Positive:**
- Full control over all routing parameters
- Can directly expose multi-criteria Pareto-optimal results
- No external service dependency — simpler infrastructure
- Deep understanding of the routing behavior

**Negative:**
- Significant development effort to implement and test
- Must handle edge cases (overnight trips, holidays, transfers) ourselves
- No community support — bugs are ours to find and fix

**Risks:**
- Performance may be a concern for complex multi-transfer queries. Mitigation: single city, single user — can optimize later if needed.
- Algorithm correctness is critical. Mitigation: comprehensive test suite with known-good route comparisons.
