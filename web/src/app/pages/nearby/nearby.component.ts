import { Component, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
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
