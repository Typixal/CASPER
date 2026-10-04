import { describe, expect, it } from "vitest"
import { describeComparison } from "./comparison"

// Shaped like collector.read_comparison() -- the real run's numbers.
const realRun = {
  reactive: { p95_ms: 2063, error_rate: 0.0518, success_pct: 93.9, replica_seconds: 623 },
  predictive: { p95_ms: 121, error_rate: 0.0, success_pct: 100.0, replica_seconds: 706 },
  verdict: { p95_ms: "predictive", error_rate: "predictive", success_pct: "predictive", replica_seconds: "reactive" },
  p95_reduction_pct: 94.2,
}

describe("describeComparison", () => {
  it("leads with how many times faster the slowest page loads were", () => {
    // 2063 / 121 = 17.0x
    expect(describeComparison(realRun).headline).toMatch(/17× faster/)
  })

  it("says how many page loads failed without CASPER and with it", () => {
    const text = describeComparison(realRun).points.join(" ")

    expect(text).toMatch(/5\.2% of page loads failed/)
    expect(text).toMatch(/none did/)
  })

  it("is honest that CASPER costs more server time", () => {
    const text = describeComparison(realRun).points.join(" ")

    expect(text).toMatch(/13% more server time/)
  })

  it("reads as a sentence, without repeating words", () => {
    // The plain term once read "server time used", which produced
    // "13% more server time used — the price of ..." on screen.
    const text = describeComparison(realRun).points.join(" ")

    expect(text).toMatch(/13% more server time —/)
  })

  it("uses engineering words in technical mode", () => {
    const text = describeComparison(realRun, true).points.join(" ")

    expect(text).toMatch(/replica-seconds/)
  })

  it("does not claim a win the data does not show", () => {
    const tie = { ...realRun, predictive: { ...realRun.reactive } }

    expect(describeComparison(tie).headline).not.toMatch(/faster/)
  })

  it("returns nothing when no experiment has run yet", () => {
    expect(describeComparison(null)).toBeNull()
  })
})
