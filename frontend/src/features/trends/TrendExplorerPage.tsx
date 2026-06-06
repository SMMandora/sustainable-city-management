import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchBikeBuckets, fetchBikeStations, type BikeStation } from "../../lib/api";

const INTERVALS = ["1m", "5m", "15m", "1h", "1d"] as const;
type Interval = (typeof INTERVALS)[number];

const WINDOWS = [
  { label: "Last hour", hours: 1 },
  { label: "Last 6 hours", hours: 6 },
  { label: "Last 24 hours", hours: 24 },
  { label: "Last 7 days", hours: 168 },
] as const;

function isoZ(d: Date): string {
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function TrendExplorerPage() {
  const stationsQuery = useQuery<BikeStation[]>({
    queryKey: ["bike-stations"],
    queryFn: fetchBikeStations,
  });
  const [stationId, setStationId] = useState<string>("");
  const [hours, setHours] = useState<number>(6);
  const [interval, setInterval] = useState<Interval>("15m");

  const { since, until } = useMemo(() => {
    const u = new Date();
    const s = new Date(u.getTime() - hours * 3600_000);
    return { since: isoZ(s), until: isoZ(u) };
  }, [hours]);

  const effectiveStationId = stationId || stationsQuery.data?.[0]?.external_id || "";

  const bucketsQuery = useQuery({
    queryKey: ["bike-buckets", effectiveStationId, since, until, interval],
    queryFn: () => fetchBikeBuckets(effectiveStationId, since, until, interval),
    enabled: !!effectiveStationId,
  });

  const stations = stationsQuery.data ?? [];
  const data = bucketsQuery.data?.buckets ?? [];

  return (
    <div style={{ padding: "1.5rem", height: "100%", display: "flex", flexDirection: "column" }}>
      <h2 style={{ marginTop: 0 }}>Bike availability over time</h2>

      <div style={{ display: "flex", gap: "1rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <label>
          Station:{" "}
          <select
            value={stationId}
            onChange={(e) => setStationId(e.target.value)}
            style={{ minWidth: 200 }}
          >
            <option value="">— select —</option>
            {stations.map((s) => (
              <option key={s.external_id} value={s.external_id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Window:{" "}
          <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            {WINDOWS.map((w) => (
              <option key={w.hours} value={w.hours}>
                {w.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Bucket:{" "}
          <select
            value={interval}
            onChange={(e) => setInterval(e.target.value as Interval)}
          >
            {INTERVALS.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ flex: 1, minHeight: 400 }}>
        {bucketsQuery.isLoading && <p>Loading…</p>}
        {bucketsQuery.error && <p>Error: {String(bucketsQuery.error)}</p>}
        {!bucketsQuery.isLoading && data.length === 0 && (
          <p>No data in the selected window.</p>
        )}
        {data.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis
                dataKey="bucket"
                stroke="#999"
                tickFormatter={(v: string) => new Date(v).toLocaleTimeString()}
              />
              <YAxis stroke="#999" />
              <Tooltip
                labelFormatter={(v) => new Date(String(v)).toLocaleString()}
                contentStyle={{ background: "#1a1a1a", border: "1px solid #444" }}
              />
              <Legend />
              <Line type="monotone" dataKey="avg_bikes" stroke="#06a77d" name="avg bikes" dot={false} />
              <Line type="monotone" dataKey="avg_stands" stroke="#f77f00" name="avg stands" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
