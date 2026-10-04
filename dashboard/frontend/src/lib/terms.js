// One vocabulary, two registers.
//
// The dashboard speaks plainly by default -- a projector audience does not
// know what a "replica" or a "p95" is. The sidebar's "show technical terms"
// switch flips every label to the engineering word, for evaluators who ask.
// Keeping both in one table means the two modes can never drift apart.

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

export function term(key, technical = false) {
  const entry = TERMS[key]
  if (!entry) {
    throw new Error(`unknown term: ${key}`)
  }
  return technical ? entry[1] : entry[0]
}

// Every term as {key, plain, technical} -- the How it works page's glossary.
export function glossary() {
  return Object.entries(TERMS).map(([key, [plain, technical]]) => ({ key, plain, technical }))
}
