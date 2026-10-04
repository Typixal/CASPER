/**
 * Exam-result-day traffic against nginx, replaying the curve from traffic.py.
 *
 * Usually run by run_comparison.py. By hand:
 *   tools\k6.exe run -e STAGES_FILE=<abs path>/stages.json -e STRATEGY=manual k6/exam_day_traffic.js
 *
 * Environment (-e):
 *   STAGES_FILE   required; absolute path, since k6's open() resolves relative
 *                 paths against this script's folder
 *   TARGET_URL    default: the nginx entrypoint
 *   STRATEGY      tag on every request (reactive | predictive)
 *   SUMMARY_FILE  where the end-of-run summary JSON is written
 */

import http from "k6/http";

const curve = JSON.parse(open(__ENV.STAGES_FILE));
const TARGET_URL = __ENV.TARGET_URL || "http://localhost:8080/results";
const STRATEGY = __ENV.STRATEGY || "unknown";

export const options = {
  discardResponseBodies: true,
  scenarios: {
    exam_day: {
      // Arrival rate, not a user pool: requests keep coming whether or not the
      // portal keeps up, so under-provisioning shows as latency and errors.
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

/**
 * Write the summary JSON for run_comparison.py and a one-line result to stdout.
 * Built by hand rather than with the remote jslib, so runs need no internet.
 * @param {object} data k6 end-of-test data.
 * @returns {object} Map of output target to content.
 */
export function handleSummary(data) {
  const out = {};
  out[__ENV.SUMMARY_FILE || "summary.json"] = JSON.stringify(data, null, 2);
  out.stdout =
    "\n[" + STRATEGY + "] requests=" + data.metrics.http_reqs.values.count +
    "  p95=" + data.metrics.http_req_duration.values["p(95)"].toFixed(1) + "ms" +
    "  failed=" + (data.metrics.http_req_failed.values.rate * 100).toFixed(2) + "%\n";
  return out;
}
