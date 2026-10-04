// CASPER Module D -- exam-result-day traffic.
//
// Replays the curve from traffic.py (quiet -> sharp ramp -> sustained peak ->
// decay) against nginx. Both comparison runs use this script with the same
// stages file, so the only difference between them is the scaling strategy.
//
// Run by run_comparison.py; by hand:
//   tools\k6.exe run -e STAGES_FILE=results/raw/stages.json -e STRATEGY=manual k6/exam_day_traffic.js
//
// Inputs (all via -e):
//   STAGES_FILE   JSON written by traffic.write_k6_config()   (required).
//                 Pass an ABSOLUTE path: k6's open() resolves relative paths
//                 against this script's folder, not the working directory.
//   TARGET_URL    defaults to the nginx entrypoint; never a portal container
//   STRATEGY      tag recorded on every request (reactive | predictive)
//   SUMMARY_FILE  where the end-of-run summary JSON is written

import http from "k6/http";

const curve = JSON.parse(open(__ENV.STAGES_FILE));
const TARGET_URL = __ENV.TARGET_URL || "http://localhost:8080/results";
const STRATEGY = __ENV.STRATEGY || "unknown";

export const options = {
  discardResponseBodies: true,
  scenarios: {
    exam_day: {
      // Arrival rate, not a fixed pool of users: requests keep coming at the
      // scheduled rate whether or not the portal keeps up -- like candidates
      // hammering refresh. Under-provisioning therefore shows up as latency
      // and errors instead of the load generator quietly backing off.
      executor: "ramping-arrival-rate",
      startRate: curve.startRate,
      timeUnit: "1s",
      preAllocatedVUs: 200,
      maxVUs: 1000,
      stages: curve.stages,
    },
  },
};

export default function () {
  http.get(TARGET_URL, { timeout: "10s", tags: { strategy: STRATEGY } });
}

// Write the end-of-run summary where run_comparison.py expects it. No remote
// jslib import for the text summary: the run must not depend on fetching
// anything from the internet.
export function handleSummary(data) {
  const out = {};
  out[__ENV.SUMMARY_FILE || "summary.json"] = JSON.stringify(data, null, 2);
  out.stdout =
    "\n[" + STRATEGY + "] requests=" + data.metrics.http_reqs.values.count +
    "  p95=" + data.metrics.http_req_duration.values["p(95)"].toFixed(1) + "ms" +
    "  failed=" + (data.metrics.http_req_failed.values.rate * 100).toFixed(2) + "%\n";
  return out;
}
