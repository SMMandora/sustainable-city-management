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
