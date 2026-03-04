# Better Transit Web App — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a minimal Angular web app with two screens (nearby stops, stop arrivals) deployed as a static site alongside the existing API.

**Architecture:** Angular 19 app in `web/` at the repo root. Standalone components with signals. Calls the existing REST API at nextstopkc.us. Deployed via SST as a static site (S3 + CloudFront) at app.nextstopkc.us. CORS is already configured to allow all origins.

**Tech Stack:** Angular 19, Angular Material, TypeScript, SST (static site deployment)

---

### Task 1: Scaffold Angular project

**Files:**
- Create: `web/` (Angular project directory)

**Step 1: Create the Angular project**

Run from repo root:

```bash
npx @angular/cli@19 new web \
  --routing=true \
  --style=scss \
  --standalone \
  --skip-git \
  --package-manager=npm
```

Flags explained:
- `--routing=true`: Creates `app.routes.ts` for client-side routing
- `--style=scss`: SCSS for styling
- `--standalone`: Standalone components (no NgModules)
- `--skip-git`: Don't init a separate git repo (we're in an existing repo)
- `--package-manager=npm`: Use npm (matches existing SST setup)

**Step 2: Add Angular Material**

```bash
cd web && npx ng add @angular/material --skip-confirmation --theme=custom --animations=included --typography=true
```

**Step 3: Configure environment files**

Create `web/src/environments/environment.ts`:

```typescript
export const environment = {
  production: false,
  apiBaseUrl: 'http://localhost:8000',
};
```

Create `web/src/environments/environment.prod.ts`:

```typescript
export const environment = {
  production: true,
  apiBaseUrl: 'https://nextstopkc.us',
};
```

Update `web/angular.json` — in the `build` architect configuration, add `fileReplacements` under the `production` configuration:

```json
"fileReplacements": [
  {
    "replace": "src/environments/environment.ts",
    "with": "src/environments/environment.prod.ts"
  }
]
```

**Step 4: Verify the scaffold builds**

```bash
cd web && npm run build
```

Expected: Build succeeds, output in `web/dist/web/browser/`

**Step 5: Add web/ to .gitignore for node_modules**

Ensure the root `.gitignore` includes:

```
web/node_modules/
web/.angular/
```

**Step 6: Commit**

```bash
git add web/ .gitignore
git commit -m "feat(web): scaffold Angular 19 project with Material"
```

---

### Task 2: API service and TypeScript interfaces

**Files:**
- Create: `web/src/app/models/stop.model.ts`
- Create: `web/src/app/models/arrival.model.ts`
- Create: `web/src/app/services/api.service.ts`

**Step 1: Create TypeScript interfaces**

These mirror the existing Pydantic models exactly.

Create `web/src/app/models/stop.model.ts`:

```typescript
import { Arrival } from './arrival.model';

export interface StopRoute {
  route_id: string;
  route_short_name: string | null;
  route_long_name: string | null;
}

export interface NearbyStop {
  stop_id: string;
  stop_name: string;
  stop_lat: number;
  stop_lon: number;
  distance_meters: number;
  routes: StopRoute[];
  next_arrivals: Arrival[];
}
```

Create `web/src/app/models/arrival.model.ts`:

```typescript
export interface Arrival {
  trip_id: string;
  route_id: string;
  headsign: string | null;
  arrival_time: string;
  departure_time: string;
  scheduled_arrival_time: string | null;
  scheduled_departure_time: string | null;
  delay_seconds: number | null;
  is_realtime: boolean;
}
```

**Step 2: Create the API service**

Create `web/src/app/services/api.service.ts`:

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { NearbyStop } from '../models/stop.model';
import { Arrival } from '../models/arrival.model';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = environment.apiBaseUrl;

  constructor(private http: HttpClient) {}

  getNearbyStops(lat: number, lon: number, radius = 800): Observable<NearbyStop[]> {
    const params = new HttpParams()
      .set('lat', lat.toString())
      .set('lon', lon.toString())
      .set('radius', radius.toString());

    return this.http.get<NearbyStop[]>(`${this.baseUrl}/stops/nearby`, { params });
  }

  getStopArrivals(stopId: string, limit = 20): Observable<Arrival[]> {
    const params = new HttpParams().set('limit', limit.toString());
    return this.http.get<Arrival[]>(`${this.baseUrl}/stops/${stopId}/arrivals`, { params });
  }
}
```

**Step 3: Register HttpClient provider**

In `web/src/app/app.config.ts`, add `provideHttpClient()`:

```typescript
import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';

import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(),
    provideAnimationsAsync(),
  ],
};
```

**Step 4: Verify it compiles**

```bash
cd web && npm run build
```

Expected: Build succeeds with no errors.

**Step 5: Commit**

```bash
git add web/src/
git commit -m "feat(web): add API service and TypeScript models"
```

---

### Task 3: Nearby Stops screen

**Files:**
- Create: `web/src/app/pages/nearby/nearby.component.ts`
- Create: `web/src/app/pages/nearby/nearby.component.html`
- Create: `web/src/app/pages/nearby/nearby.component.scss`
- Modify: `web/src/app/app.routes.ts`
- Modify: `web/src/app/app.component.ts`
- Modify: `web/src/app/app.component.html`

**Step 1: Create the nearby stops component**

Create `web/src/app/pages/nearby/nearby.component.ts`:

```typescript
import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../services/api.service';
import { NearbyStop } from '../../models/stop.model';
import { Arrival } from '../../models/arrival.model';

@Component({
  selector: 'app-nearby',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatIconModule,
  ],
  templateUrl: './nearby.component.html',
  styleUrl: './nearby.component.scss',
})
export class NearbyComponent implements OnInit, OnDestroy {
  stops = signal<NearbyStop[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  private refreshInterval: ReturnType<typeof setInterval> | null = null;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.requestLocation();
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  private requestLocation(): void {
    if (!navigator.geolocation) {
      this.error.set('Geolocation is not supported by your browser.');
      this.loading.set(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const lat = position.coords.latitude;
        const lon = position.coords.longitude;
        this.loadStops(lat, lon);
        this.refreshInterval = setInterval(() => this.loadStops(lat, lon), 30_000);
      },
      () => {
        this.error.set('Location access denied. Please enable location services.');
        this.loading.set(false);
      },
    );
  }

  private loadStops(lat: number, lon: number): void {
    this.api.getNearbyStops(lat, lon).subscribe({
      next: (stops) => {
        this.stops.set(stops);
        this.loading.set(false);
        this.error.set(null);
      },
      error: () => {
        this.error.set('Failed to load nearby stops.');
        this.loading.set(false);
      },
    });
  }

  minutesUntil(arrival: Arrival): string {
    const arrivalDate = new Date(arrival.arrival_time);
    const now = new Date();
    const diffMs = arrivalDate.getTime() - now.getTime();
    const diffMin = Math.round(diffMs / 60_000);

    if (diffMin <= 0) return 'Now';
    if (diffMin === 1) return '1 min';
    return `${diffMin} min`;
  }

  formatDistance(meters: number): string {
    if (meters < 1000) {
      return `${Math.round(meters)}m`;
    }
    return `${(meters / 1000).toFixed(1)}km`;
  }
}
```

**Step 2: Create the template**

Create `web/src/app/pages/nearby/nearby.component.html`:

```html
<div class="nearby-container">
  <h1>Nearby Stops</h1>

  @if (loading()) {
    <div class="loading">
      <mat-spinner diameter="40"></mat-spinner>
      <p>Finding stops near you...</p>
    </div>
  }

  @if (error(); as errorMsg) {
    <div class="error">
      <mat-icon>error</mat-icon>
      <p>{{ errorMsg }}</p>
    </div>
  }

  @for (stop of stops(); track stop.stop_id) {
    <mat-card class="stop-card" [routerLink]="['/stops', stop.stop_id]">
      <mat-card-header>
        <mat-card-title>{{ stop.stop_name }}</mat-card-title>
        <mat-card-subtitle>{{ formatDistance(stop.distance_meters) }} away</mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        @if (stop.routes.length > 0) {
          <div class="routes">
            @for (route of stop.routes; track route.route_id) {
              <span class="route-badge">{{ route.route_short_name || route.route_id }}</span>
            }
          </div>
        }

        @if (stop.next_arrivals.length > 0) {
          <div class="arrivals">
            @for (arrival of stop.next_arrivals; track arrival.trip_id) {
              <div class="arrival-row">
                <span class="route-name">{{ arrival.route_id }}</span>
                <span class="headsign">{{ arrival.headsign }}</span>
                <span class="time" [class.realtime]="arrival.is_realtime">
                  {{ minutesUntil(arrival) }}
                </span>
              </div>
            }
          </div>
        } @else {
          <p class="no-arrivals">No upcoming arrivals</p>
        }
      </mat-card-content>
    </mat-card>
  }

  @if (!loading() && !error() && stops().length === 0) {
    <p class="no-stops">No stops found nearby.</p>
  }
</div>
```

**Step 3: Create the styles**

Create `web/src/app/pages/nearby/nearby.component.scss`:

```scss
.nearby-container {
  max-width: 600px;
  margin: 0 auto;
  padding: 16px;

  h1 {
    font-size: 1.5rem;
    margin-bottom: 16px;
  }
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 0;

  p {
    margin-top: 16px;
    color: rgba(0, 0, 0, 0.6);
  }
}

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #fdecea;
  border-radius: 8px;
  color: #d32f2f;
}

.stop-card {
  margin-bottom: 12px;
  cursor: pointer;

  &:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
  }
}

.routes {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.route-badge {
  background: #1976d2;
  color: white;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 500;
}

.arrivals {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.arrival-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;

  .route-name {
    font-weight: 600;
    min-width: 40px;
  }

  .headsign {
    flex: 1;
    color: rgba(0, 0, 0, 0.6);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .time {
    font-weight: 600;
    white-space: nowrap;

    &.realtime {
      color: #2e7d32;
    }
  }
}

.no-arrivals,
.no-stops {
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
  padding: 16px;
}
```

**Step 4: Set up routing and app shell**

Replace `web/src/app/app.routes.ts`:

```typescript
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./pages/nearby/nearby.component').then((m) => m.NearbyComponent),
  },
  {
    path: 'stops/:stopId',
    loadComponent: () =>
      import('./pages/stop-arrivals/stop-arrivals.component').then(
        (m) => m.StopArrivalsComponent,
      ),
  },
];
```

Replace `web/src/app/app.component.ts`:

```typescript
import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, MatToolbarModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {}
```

Replace `web/src/app/app.component.html`:

```html
<mat-toolbar color="primary">
  <a routerLink="/" style="color: inherit; text-decoration: none;">
    Next Stop KC
  </a>
</mat-toolbar>

<router-outlet />
```

**Step 5: Build and verify**

The build will fail because `StopArrivalsComponent` doesn't exist yet. That's expected — we'll create it in Task 4. Verify the nearby component compiles by temporarily removing the stop-arrivals route:

```bash
cd web && npm run build
```

If it fails due to the missing component, comment out the stop-arrivals route in `app.routes.ts` temporarily, verify the build passes, then restore it.

**Step 6: Commit**

```bash
git add web/src/
git commit -m "feat(web): add nearby stops screen with auto-refresh"
```

---

### Task 4: Stop Arrivals screen

**Files:**
- Create: `web/src/app/pages/stop-arrivals/stop-arrivals.component.ts`
- Create: `web/src/app/pages/stop-arrivals/stop-arrivals.component.html`
- Create: `web/src/app/pages/stop-arrivals/stop-arrivals.component.scss`

**Step 1: Create the stop arrivals component**

Create `web/src/app/pages/stop-arrivals/stop-arrivals.component.ts`:

```typescript
import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatButtonModule } from '@angular/material/button';
import { ApiService } from '../../services/api.service';
import { Arrival } from '../../models/arrival.model';

interface RouteGroup {
  route_id: string;
  arrivals: Arrival[];
}

@Component({
  selector: 'app-stop-arrivals',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatButtonModule,
  ],
  templateUrl: './stop-arrivals.component.html',
  styleUrl: './stop-arrivals.component.scss',
})
export class StopArrivalsComponent implements OnInit, OnDestroy {
  stopId = '';
  arrivals = signal<Arrival[]>([]);
  loading = signal(true);
  error = signal<string | null>(null);

  groupedArrivals = computed(() => {
    const groups = new Map<string, Arrival[]>();
    for (const arrival of this.arrivals()) {
      const key = arrival.route_id;
      if (!groups.has(key)) {
        groups.set(key, []);
      }
      groups.get(key)!.push(arrival);
    }
    return Array.from(groups.entries()).map(
      ([route_id, arrivals]): RouteGroup => ({ route_id, arrivals }),
    );
  });

  private refreshInterval: ReturnType<typeof setInterval> | null = null;

  constructor(
    private route: ActivatedRoute,
    private api: ApiService,
  ) {}

  ngOnInit(): void {
    this.stopId = this.route.snapshot.paramMap.get('stopId') || '';
    if (this.stopId) {
      this.loadArrivals();
      this.refreshInterval = setInterval(() => this.loadArrivals(), 30_000);
    }
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  private loadArrivals(): void {
    this.api.getStopArrivals(this.stopId).subscribe({
      next: (arrivals) => {
        this.arrivals.set(arrivals);
        this.loading.set(false);
        this.error.set(null);
      },
      error: () => {
        this.error.set('Failed to load arrivals.');
        this.loading.set(false);
      },
    });
  }

  minutesUntil(arrival: Arrival): string {
    const arrivalDate = new Date(arrival.arrival_time);
    const now = new Date();
    const diffMs = arrivalDate.getTime() - now.getTime();
    const diffMin = Math.round(diffMs / 60_000);

    if (diffMin <= 0) return 'Now';
    if (diffMin === 1) return '1 min';
    return `${diffMin} min`;
  }

  formatDelay(seconds: number | null): string | null {
    if (seconds === null || seconds === 0) return null;
    const min = Math.round(seconds / 60);
    if (min <= 0) return null;
    return `${min} min late`;
  }
}
```

**Step 2: Create the template**

Create `web/src/app/pages/stop-arrivals/stop-arrivals.component.html`:

```html
<div class="arrivals-container">
  <div class="header">
    <a mat-icon-button routerLink="/">
      <mat-icon>arrow_back</mat-icon>
    </a>
    <h1>Stop {{ stopId }}</h1>
  </div>

  @if (loading()) {
    <div class="loading">
      <mat-spinner diameter="40"></mat-spinner>
      <p>Loading arrivals...</p>
    </div>
  }

  @if (error(); as errorMsg) {
    <div class="error">
      <mat-icon>error</mat-icon>
      <p>{{ errorMsg }}</p>
    </div>
  }

  @for (group of groupedArrivals(); track group.route_id) {
    <mat-card class="route-group">
      <mat-card-header>
        <mat-card-title>
          <span class="route-badge">{{ group.route_id }}</span>
        </mat-card-title>
      </mat-card-header>

      <mat-card-content>
        @for (arrival of group.arrivals; track arrival.trip_id) {
          <div class="arrival-row">
            <div class="arrival-info">
              <span class="headsign">{{ arrival.headsign || 'Unknown' }}</span>
              @if (formatDelay(arrival.delay_seconds); as delay) {
                <span class="delay">{{ delay }}</span>
              }
            </div>
            <div class="arrival-time">
              <span class="countdown" [class.realtime]="arrival.is_realtime">
                {{ minutesUntil(arrival) }}
              </span>
              @if (arrival.is_realtime) {
                <mat-icon class="rt-icon">gps_fixed</mat-icon>
              }
            </div>
          </div>
        }
      </mat-card-content>
    </mat-card>
  }

  @if (!loading() && !error() && groupedArrivals().length === 0) {
    <p class="no-arrivals">No upcoming arrivals at this stop.</p>
  }
</div>
```

**Step 3: Create the styles**

Create `web/src/app/pages/stop-arrivals/stop-arrivals.component.scss`:

```scss
.arrivals-container {
  max-width: 600px;
  margin: 0 auto;
  padding: 16px;
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;

  h1 {
    font-size: 1.5rem;
    margin: 0;
  }
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 0;

  p {
    margin-top: 16px;
    color: rgba(0, 0, 0, 0.6);
  }
}

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  background: #fdecea;
  border-radius: 8px;
  color: #d32f2f;
}

.route-group {
  margin-bottom: 12px;
}

.route-badge {
  background: #1976d2;
  color: white;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.9rem;
  font-weight: 500;
}

.arrival-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);

  &:last-child {
    border-bottom: none;
  }
}

.arrival-info {
  display: flex;
  flex-direction: column;

  .headsign {
    font-size: 0.95rem;
  }

  .delay {
    font-size: 0.8rem;
    color: #e65100;
  }
}

.arrival-time {
  display: flex;
  align-items: center;
  gap: 4px;

  .countdown {
    font-size: 1.1rem;
    font-weight: 600;

    &.realtime {
      color: #2e7d32;
    }
  }

  .rt-icon {
    font-size: 16px;
    width: 16px;
    height: 16px;
    color: #2e7d32;
  }
}

.no-arrivals {
  color: rgba(0, 0, 0, 0.6);
  text-align: center;
  padding: 32px;
}
```

**Step 4: Build and verify**

```bash
cd web && npm run build
```

Expected: Build succeeds.

**Step 5: Commit**

```bash
git add web/src/
git commit -m "feat(web): add stop arrivals screen with grouped routes"
```

---

### Task 5: Local dev testing

**Files:**
- Modify: `web/src/environments/environment.ts` (if needed)

**Step 1: Start the API locally**

In one terminal:

```bash
cd api && uv run fastapi dev src/better_transit/main.py
```

**Step 2: Start the Angular dev server**

In another terminal:

```bash
cd web && npm start
```

This serves at `http://localhost:4200`. The API runs at `http://localhost:8000`.

**Step 3: Test the nearby stops screen**

Open `http://localhost:4200` in a browser. Allow location access when prompted. Verify:
- Stops load and display with distances
- Route badges appear
- Next arrivals show with countdown times

**Step 4: Test the stop arrivals screen**

Click a stop card. Verify:
- Navigates to `/stops/{stop_id}`
- Arrivals load grouped by route
- Real-time indicator shows when applicable
- Back button returns to nearby stops

**Step 5: Fix any issues found**

If CORS errors appear, add CORS middleware to `api/src/better_transit/main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 6: Commit any fixes**

```bash
git add -A
git commit -m "fix(web): local dev fixes"
```

---

### Task 6: SST static site deployment

**Files:**
- Modify: `sst.config.ts`

**Step 1: Add StaticSite to SST config**

In `sst.config.ts`, inside the `run()` function, after the `api.route` call and before the `return`, add:

```typescript
    // --- Web App (Static Site) ---
    const webDomain =
      $app.stage === "production"
        ? "app.nextstopkc.us"
        : `app-${$app.stage}.nextstopkc.us`;

    const web = new sst.aws.StaticSite("Web", {
      path: "web",
      build: {
        command: "npm run build",
        output: "dist/web/browser",
      },
      environment: {
        NG_APP_API_BASE_URL: api.url,
      },
      domain: {
        name: webDomain,
        dns: sst.aws.dns(),
      },
    });
```

Update the return statement to include the web URL:

```typescript
    return {
      api: api.url,
      domain: domain,
      web: web.url,
      webDomain: webDomain,
    };
```

**Step 2: Verify SST config parses**

```bash
npx sst diff
```

This should show the new StaticSite resource.

**Step 3: Commit**

```bash
git add sst.config.ts
git commit -m "infra: add SST StaticSite for web app deployment"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Scaffold Angular project + Material | web/ (new) |
| 2 | API service + TypeScript models | web/src/app/services/, models/ |
| 3 | Nearby stops screen | web/src/app/pages/nearby/ |
| 4 | Stop arrivals screen | web/src/app/pages/stop-arrivals/ |
| 5 | Local dev testing | Fix any issues found |
| 6 | SST static site deployment | sst.config.ts |
