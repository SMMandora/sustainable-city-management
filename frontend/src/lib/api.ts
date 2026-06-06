const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export interface BikeStation {
  external_id: string;
  name: string;
  latitude: string;
  longitude: string;
  capacity: number;
  first_seen_at: string;
  last_seen_at: string;
}

export interface BikeAvailability {
  station_external_id: string;
  station_name: string;
  observed_at: string;
  bikes_available: number;
  stands_available: number;
  status: "OPEN" | "CLOSED";
}

interface CursorPage<T> {
  results: T[];
  next: string | null;
  previous: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} on ${url}`);
  }
  return (await response.json()) as T;
}

export function fetchBikeStations(): Promise<BikeStation[]> {
  return getJson<BikeStation[]>("/api/v1/bike-stations/");
}

export interface BikeBucket {
  bucket: string;
  sample_count: number;
  avg_bikes: number;
  avg_stands: number;
}

export interface BikeBucketResponse {
  station_external_id: string;
  interval: string;
  since: string;
  until: string;
  buckets: BikeBucket[];
}

export function fetchBikeBuckets(
  stationId: string,
  since: string,
  until: string,
  interval: string,
): Promise<BikeBucketResponse> {
  const params = new URLSearchParams({ station: stationId, since, until, interval });
  return getJson<BikeBucketResponse>(`/api/v1/bike-availability/buckets/?${params}`);
}

export interface NoiseSensor {
  external_id: string;
  label: string;
  latitude: string;
  longitude: string;
  first_seen_at: string;
  last_seen_at: string;
}

export interface NoiseReading {
  sensor_external_id: string;
  sensor_label: string;
  observed_at: string;
  laeq_db: string;
}

export function fetchNoiseSensors(): Promise<NoiseSensor[]> {
  return getJson<NoiseSensor[]>("/api/v1/noise-sensors/");
}

export async function fetchLatestNoiseReadings(): Promise<NoiseReading[]> {
  const since = new Date(Date.now() - 24 * 3600_000).toISOString().replace(/\.\d{3}Z$/, "Z");
  let url: string | null = `/api/v1/noise-readings/?since=${encodeURIComponent(since)}`;
  const all: NoiseReading[] = [];
  while (url) {
    const page: CursorPage<NoiseReading> = await getJson(url);
    all.push(...page.results);
    url = page.next;
  }
  const latest = new Map<string, NoiseReading>();
  for (const r of all) {
    const existing = latest.get(r.sensor_external_id);
    if (!existing || r.observed_at > existing.observed_at) {
      latest.set(r.sensor_external_id, r);
    }
  }
  return Array.from(latest.values());
}

export async function fetchLatestBikeAvailability(): Promise<BikeAvailability[]> {
  // JCDecaux's `last_reported` reflects when each station actually reported,
  // not when we polled. Many stations report less frequently than every hour,
  // so we use a 24h window to make sure every station shows up at least once.
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
  let url: string | null = `/api/v1/bike-availability/?since=${encodeURIComponent(since)}`;
  const all: BikeAvailability[] = [];
  while (url) {
    const page: CursorPage<BikeAvailability> = await getJson(url);
    all.push(...page.results);
    url = page.next;
  }
  // Keep only the latest observation per station.
  const latest = new Map<string, BikeAvailability>();
  for (const obs of all) {
    const existing = latest.get(obs.station_external_id);
    if (!existing || obs.observed_at > existing.observed_at) {
      latest.set(obs.station_external_id, obs);
    }
  }
  return Array.from(latest.values());
}
