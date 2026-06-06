import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

interface DeltaPayload {
  source: string;
  feed: string;
  upserted: number;
}

/**
 * Subscribe to an SSE topic. On each `delta` event, invalidate the
 * provided React Query keys so they refetch.
 *
 * Usage:
 *   useEventSource("bikes", [["bike-availability-latest"]]);
 */
export function useEventSource(topic: string, invalidateKeys: readonly (readonly unknown[])[]): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const url = `${API_BASE}/api/v1/stream/${topic}`;
    const sse = new EventSource(url);

    sse.addEventListener("delta", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data) as DeltaPayload;
        if (data.upserted > 0) {
          for (const key of invalidateKeys) {
            queryClient.invalidateQueries({ queryKey: key });
          }
        }
      } catch {
        // Ignore malformed events.
      }
    });

    sse.onerror = () => {
      // EventSource auto-reconnects; just log to console for diagnostics.
      console.warn(`[sse] ${topic} disconnected`);
    };

    return () => sse.close();
  }, [topic, queryClient, invalidateKeys]);
}
