// k6 load test for the query API.
// Runs 100 req/s sustained for 10 minutes against /api/v1/bike-availability/
// with a since= cursor at the upper end of what a real dashboard would request.
// Pass: p(95) latency < 200ms AND <1% error rate.
//
// Run locally: just load-test
// Override: BASE_URL=http://scm.localtest.me k6 run tests/load/query-api.js

import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  scenarios: {
    queries: {
      executor: "constant-arrival-rate",
      rate: 100,
      timeUnit: "1s",
      duration: "10m",
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<200"],
    http_req_failed: ["rate<0.01"],
  },
};

function isoZ(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

export default function () {
  // Hot read path: "last 24h of availability." Realistic dashboard query.
  const since = isoZ(Date.now() - 24 * 3600_000);
  const params = `since=${encodeURIComponent(since)}`;
  const url = `${BASE_URL}/api/v1/bike-availability/?${params}`;
  const response = http.get(url);
  check(response, {
    "200 OK": (r) => r.status === 200,
    "paginated body": (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.results);
      } catch (_) {
        return false;
      }
    },
  });
}
