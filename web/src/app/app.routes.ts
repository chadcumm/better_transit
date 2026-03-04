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
