import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import ExperimentPage from "./ExperimentPage"

const comparison = {
  reactive: { p95_ms: 2063, error_rate: 0.0518, success_pct: 93.9, replica_seconds: 623 },
  predictive: { p95_ms: 121, error_rate: 0, success_pct: 100, replica_seconds: 706 },
  verdict: { p95_ms: "predictive", error_rate: "predictive", success_pct: "predictive", replica_seconds: "reactive" },
  p95_reduction_pct: 94.2,
}

describe("ExperimentPage", () => {
  it("explains how to produce a result when none exists yet", () => {
    render(<ExperimentPage comparison={null} />)

    expect(screen.getByText(/run-demo\.ps1 -Compare/)).toBeInTheDocument()
  })

  it("leads with the plain-English verdict", () => {
    render(<ExperimentPage comparison={comparison} />)

    expect(screen.getByRole("heading", { name: /17× faster/ })).toBeInTheDocument()
    expect(screen.getByText(/5\.2% of page loads failed/)).toBeInTheDocument()
  })

  it("explains why the test is fair, in plain words", () => {
    render(<ExperimentPage comparison={comparison} />)

    expect(screen.getByText(/same visitors/i)).toBeInTheDocument()
  })

  it("shows the report's charts", () => {
    render(<ExperimentPage comparison={comparison} />)

    expect(screen.getByRole("img", { name: /over time/i })).toHaveAttribute("src", "/api/results/latency_over_time.png")
    expect(screen.getByRole("img", { name: /side by side/i })).toHaveAttribute("src", "/api/results/summary_bars.png")
  })

  it("labels the results table plainly by default", () => {
    render(<ExperimentPage comparison={comparison} />)

    expect(screen.getByRole("cell", { name: "slowest page loads" })).toBeInTheDocument()
  })

  it("labels the results table technically in technical mode", () => {
    render(<ExperimentPage comparison={comparison} technical />)

    expect(screen.getByRole("cell", { name: "p95 latency" })).toBeInTheDocument()
  })
})
