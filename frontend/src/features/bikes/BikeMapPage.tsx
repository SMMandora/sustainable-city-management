import { useQuery } from "@tanstack/react-query";
import L from "leaflet";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import {
  fetchBikeStations,
  fetchLatestBikeAvailability,
  type BikeAvailability,
  type BikeStation,
} from "../../lib/api";
import { useEventSource } from "../../lib/sse";

const BIKE_INVALIDATE_KEYS = [["bike-availability-latest"]] as const;

// Default Leaflet markers don't resolve in Vite without this; we use CircleMarker
// to avoid that issue entirely. This shim is kept for any future Marker usage.
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: unknown })._getIconUrl;

const DUBLIN: [number, number] = [53.349805, -6.260310];

function markerColor(bikes: number, capacity: number): string {
  if (capacity === 0) return "#888";
  const ratio = bikes / capacity;
  if (ratio === 0) return "#d62828";
  if (ratio < 0.25) return "#f77f00";
  if (ratio < 0.5) return "#fcbf49";
  return "#06a77d";
}

export function BikeMapPage() {
  const stationsQuery = useQuery<BikeStation[]>({
    queryKey: ["bike-stations"],
    queryFn: fetchBikeStations,
  });
  const availabilityQuery = useQuery<BikeAvailability[]>({
    queryKey: ["bike-availability-latest"],
    queryFn: fetchLatestBikeAvailability,
    refetchInterval: 60_000,
  });

  // Push: refetch availability whenever a bike-ingest poll finishes.
  useEventSource("bikes", BIKE_INVALIDATE_KEYS);

  if (stationsQuery.isLoading || availabilityQuery.isLoading) {
    return <div style={{ padding: "2rem" }}>Loading…</div>;
  }
  if (stationsQuery.error) {
    return <div style={{ padding: "2rem" }}>Failed to load stations: {String(stationsQuery.error)}</div>;
  }

  const stations = stationsQuery.data ?? [];
  const availability = availabilityQuery.data ?? [];
  const availByStation = new Map(availability.map((a) => [a.station_external_id, a]));

  return (
    <MapContainer center={DUBLIN} zoom={13} style={{ height: "100%", width: "100%" }}>
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      {stations.map((s) => {
        const a = availByStation.get(s.external_id);
        const color = a ? markerColor(a.bikes_available, s.capacity) : "#888";
        return (
          <CircleMarker
            key={s.external_id}
            center={[Number(s.latitude), Number(s.longitude)]}
            radius={7}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.8, weight: 1 }}
          >
            <Popup>
              <strong>{s.name}</strong>
              <br />
              {a ? (
                <>
                  {a.bikes_available} bikes / {a.stands_available} stands
                  <br />
                  <small>{a.status} · {new Date(a.observed_at).toLocaleTimeString()}</small>
                </>
              ) : (
                <small>no data in last hour</small>
              )}
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
