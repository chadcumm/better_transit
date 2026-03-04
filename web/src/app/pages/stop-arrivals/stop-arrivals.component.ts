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
