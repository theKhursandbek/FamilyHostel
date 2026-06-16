// k6 smoke test for the Mini App API.
//
//   docker run --rm -i -e BASE=https://staging.example.com/api/v1 \
//     -e TOKEN=<jwt> grafana/k6 run - < load.js
//
// Targets the public/read-mostly surface that the Mini App hits on cold
// launch. We deliberately avoid mutating endpoints in this baseline run.

import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  scenarios: {
    cold_launch: {
      executor: "ramping-vus",
      startVUs: 1,
      stages: [
        { duration: "30s", target: 20 },
        { duration: "1m",  target: 20 },
        { duration: "20s", target: 0 },
      ],
      gracefulRampDown: "10s",
    },
  },
  thresholds: {
    http_req_failed:   ["rate<0.02"],
    http_req_duration: ["p(95)<800"],
  },
};

const BASE = __ENV.BASE  || "http://localhost:8000/api/v1";
const TOKEN = __ENV.TOKEN || "";

const headers = TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};

export default function () {
  const r1 = http.get(`${BASE}/public/branches/`, { headers });
  check(r1, { "branches 200": (r) => r.status === 200 });

  const r2 = http.get(`${BASE}/public/rooms/?status=available&limit=10`, { headers });
  check(r2, { "rooms 200": (r) => r.status === 200 });

  if (TOKEN) {
    const r3 = http.get(`${BASE}/bookings/my/`, { headers });
    check(r3, { "my bookings 2xx": (r) => r.status >= 200 && r.status < 300 });
  }
  sleep(1);
}
