// Every label in plain and technical form, in one table so the two modes
// cannot drift apart.

const TERMS = {
  replicas: ["servers", "replicas"],
  replica: ["server", "replica"],
  p95: ["slowest page loads", "p95 latency"],
  median: ["typical page load", "median latency"],
  error_rate: ["failed page loads", "error rate"],
  success_pct: ["pages that loaded", "% successful requests"],
  replica_seconds: ["server time", "replica-seconds"],
  dropped: ["visitors turned away", "dropped iterations"],
  nginx: ["traffic director", "nginx upstream"],
  probe: ["test visitor", "latency probe"],
  reactive: ["wait-and-react autoscaler", "reactive baseline"],
  predictive: ["CASPER (plans ahead)", "predictive policy"],
  manual: ["by hand", "manual"],
  ramp_start: ["get ready", "ramp_start"],
  ramp_peak: ["busiest moment", "ramp_peak"],
  ramp_end: ["wind down", "ramp_end"],
  candidates: ["students registered", "registered_candidates"],
  prediction: ["forecast", "Prediction"],
}

/**
 * Label for a term in the current mode.
 * @param {string} key A TERMS key.
 * @param {boolean} [technical=false]
 * @returns {string}
 * @throws {Error} On an unknown key.
 */
export function term(key, technical = false) {
  const entry = TERMS[key]
  if (!entry) {
    throw new Error(`unknown term: ${key}`)
  }
  return technical ? entry[1] : entry[0]
}

/**
 * @returns {{key: string, plain: string, technical: string}[]} All terms, for the glossary.
 */
export function glossary() {
  return Object.entries(TERMS).map(([key, [plain, technical]]) => ({ key, plain, technical }))
}
