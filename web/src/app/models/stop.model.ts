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
