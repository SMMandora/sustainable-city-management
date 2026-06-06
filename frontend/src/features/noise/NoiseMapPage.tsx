import { useQuery } from "@tanstack/react-query";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import {
  fetchLatestNoiseReadings,
  fetchNoiseSensors,
  type NoiseReading,
  type NoiseSensor,
} from "../../lib/api";
import { useEventSource } from "../../lib/sse";

const NOISE_INVALIDATE_KEYS = [["noise-readings-latest"]] as const;
const DUBLIN: [number, number] = [53.349805, -6.260310];

function noiseColor(db: number): string {
  if (db < 50) return "#06a77d"; // quiet
  if (db < 65) return "#fcbf49"; // moderate
  if (db < 75) return "#f77f00"; // loud
  return "#d62828"; // very loud
}

export function NoiseMapPage() {
  const sensorsQuery = useQuery<NoiseSensor[]>({
    queryKey: ["noise-sensors"],
    queryFn: fetchNoiseSensors,
  });
  const readingsQuery = useQuery<NoiseReading[]>({
    queryKey: ["noise-readings-latest"],
    queryFn: fetchLatestNoiseReadings,
    refetchInterval: 60_000,
  });
  useEventSource("noise", NOISE_INVALIDATE_KEYS);

  if (sensorsQuery.isLoading) {
    return <div style={{ padding: "2rem" }}>Loading…</div>;
  }

  const sensors = sensorsQuery.data ?? [];
  const readings = readingsQuery.data ?? [];
  const readingsBySensor = new Map(readings.map((r) => [r.sensor_external_id, r]));

  if (sensors.length === 0) {
    return (
      <div style={{ padding: "2rem" }}>
        <h2>No noise sensors loaded</h2>
        <p>
          The Sonitus data source requires registration with Smart Dublin Cloud. To enable, set{" "}
          <code>SONITUS_USERNAME</code> and <code>SONITUS_PASSWORD</code> in{" "}
          <code>services/backend/.env</code>, then flip the <code>sonitus</code> DataSource row to{" "}
          <code>enabled=true</code>.
        </p>
      </div>
    );
  }

  return (
    <MapContainer center={DUBLIN} zoom={13} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      {sensors.map((s) => {
        const r = readingsBySensor.get(s.external_id);
        const db = r ? Number(r.laeq_db) : null;
        const color = db === null ? "#888" : noiseColor(db);
        const radius = db === null ? 6 : Math.max(6, Math.min(20, (db - 40) / 2));
        return (
          <CircleMarker
            key={s.external_id}
            center={[Number(s.latitude), Number(s.longitude)]}
            radius={radius}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.6, weight: 1 }}
          >
            <Popup>
              <strong>{s.label}</strong>
              <br />
              {r ? (
                <>
                  {Number(r.laeq_db).toFixed(1)} dB(A) LAeq
                  <br />
                  <small>{new Date(r.observed_at).toLocaleTimeString()}</small>
                </>
              ) : (
                <small>no reading in last 24h</small>
              )}
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
