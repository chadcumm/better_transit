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
