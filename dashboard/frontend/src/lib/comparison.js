// Plain-English summary of Module D's result. Never claims a win the numbers
// do not show, and always states what CASPER cost.

import { term } from "./terms"

const pct = (v) => `${(v * 100).toFixed(1)}%`

function timesFaster(slow, fast) {
  const ratio = slow / fast
  return ratio >= 10 ? Math.round(ratio).toString() : ratio.toFixed(1)
}

/**
 * Describe the experiment result for the page.
 * @param {object|null} c Output of collector.read_comparison().
 * @param {boolean} [technical=false] Use engineering terms.
 * @returns {{headline: string, points: string[]}|null} Null when there is no result.
 */
export function describeComparison(c, technical = false) {
  if (!c) return null
  const r = c.reactive
  const p = c.predictive

  const headline =
    p.p95_ms < r.p95_ms
      ? `With CASPER, the ${term("p95", technical)} were ${timesFaster(r.p95_ms, p.p95_ms)}× faster`
      : p.p95_ms === r.p95_ms
        ? "Both strategies performed the same in this run"
        : "CASPER did not beat the autoscaler in this run"

  const points = []

  if (technical) {
    points.push(`Error rate: ${term("reactive", true)} ${pct(r.error_rate)}, ${term("predictive", true)} ${pct(p.error_rate)}.`)
  } else {
    const withCasper = p.error_rate === 0 ? "none did" : `${pct(p.error_rate)} did`
    points.push(`Without CASPER, ${pct(r.error_rate)} of page loads failed; with CASPER, ${withCasper}.`)
  }

  points.push(
    `${p.success_pct.toFixed(1)}% of ${technical ? "requests succeeded" : "pages loaded"} with CASPER, versus ${r.success_pct.toFixed(1)}% without.`,
  )

  const costChange = ((p.replica_seconds - r.replica_seconds) / r.replica_seconds) * 100
  const servers = term("replicas", technical)
  if (costChange > 0) {
    points.push(
      `CASPER used ${Math.round(costChange)}% more ${term("replica_seconds", technical)} — the price of having ${servers} ready before students arrived.`,
    )
  } else {
    points.push(`CASPER also used ${Math.round(-costChange)}% less ${term("replica_seconds", technical)}.`)
  }

  return { headline, points }
}
