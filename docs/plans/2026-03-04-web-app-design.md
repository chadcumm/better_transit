# Better Transit Web App — Design

**Goal:** A minimal Angular web app with two screens — nearby stops and stop arrivals — so the app is usable from a phone browser while the full iOS app is developed.

## Architecture

Angular app in `web/` at the repo root. Calls the existing REST API at `nextstopkc.us`. Deployed as a static site via SST (S3 + CloudFront) at `app.nextstopkc.us`.

No backend changes except adding the web app's origin to CORS allowed origins.

## Screens

### 1. Nearby Stops (home screen)

- Request browser geolocation on load
- Call `GET /stops/nearby?lat=X&lon=Y`
- List stops sorted by distance, each showing:
  - Stop name and distance ("150m away")
  - Routes serving it (colored badges)
  - Next 3 arrivals with countdown ("5 min", "12 min")
- Auto-refresh arrivals every 30 seconds
- Fallback if geolocation denied: text input for location (geocode via browser API or simple lat/lon entry)

### 2. Stop Arrivals (tap a stop)

- Call `GET /stops/{stop_id}/arrivals`
- All upcoming arrivals grouped by route
- Real-time indicator vs scheduled
- Delay info when available ("2 min late")
- Auto-refresh every 30 seconds

## Tech Stack

- Angular 19 (standalone components, signals)
- Angular Material for UI components
- Mobile-first responsive design
- Environment config for API base URL

## Deployment

- SST StaticSite resource in `sst.config.ts`
- S3 bucket + CloudFront distribution
- Domain: `app.nextstopkc.us`
- Build: `ng build` outputs to `web/dist/`

## What doesn't change

- No new API endpoints
- No backend logic changes (only CORS config)
- No authentication
