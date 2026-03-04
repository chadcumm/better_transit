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
