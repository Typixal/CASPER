import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import OverviewPage from "./OverviewPage"

const state = (overrides = {}) => ({
  generated_at: "2026-10-04T12:00:00+00:00",
  docker: { available: true, replicas: [] },
  summary: { replicas_ready: 4, replicas_total: 4, last_source: "predictive" },
  probe: { enabled: true, ok: true, latency_ms: 121.4 },
  scale_log: { last: { timestamp: "2026-10-04T11:59:00+00:00" } },
  prediction: { exists: true, event_id: "cbse_class12_2026", phase: "ramp", peak_replicas: 4, seconds_to_next: 30 },
  schedule: [],
  modules: { d: { comparison: null } },
  ...overrides,
})

describe("OverviewPage", () => {
  it("leads with a plain sentence about what is happening", () => {
    render(<OverviewPage state={state()} onNavigate={() => {}} />)

    expect(screen.getByRole("heading", { name: /students are arriving/i })).toBeInTheDocument()
  })

  it("shows the key numbers in plain words", () => {
    render(<OverviewPage state={state()} onNavigate={() => {}} />)

    expect(screen.getByText("servers ready")).toBeInTheDocument()
    expect(screen.getByText("0.12 s")).toBeInTheDocument() // typical page load
    expect(screen.getByText("CASPER (plans ahead)")).toBeInTheDocument() // last change made by
  })

  it("says the test visitor is off rather than showing a blank latency", () => {
    render(<OverviewPage state={state({ probe: { enabled: false } })} onNavigate={() => {}} />)

    expect(screen.getByText(/test visitor off/i)).toBeInTheDocument()
  })

  it("teases the experiment result and links to it when one exists", async () => {
    const onNavigate = vi.fn()
    const comparison = {
      reactive: { p95_ms: 2063, error_rate: 0.0518, success_pct: 93.9, replica_seconds: 623 },
      predictive: { p95_ms: 121, error_rate: 0, success_pct: 100, replica_seconds: 706 },
      verdict: {},
      p95_reduction_pct: 94.2,
    }
    render(<OverviewPage state={state({ modules: { d: { comparison } } })} onNavigate={onNavigate} />)

    expect(screen.getByText(/17× faster/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: /see the experiment/i }))
    expect(onNavigate).toHaveBeenCalledWith("experiment")
  })

  it("names the next upcoming event from the schedule", () => {
    const schedule = [
      { event_id: "cbse_class12_2026", date: "2026-05-13T10:00:00+05:30", status: "past", predicted_peak_replicas: 13 },
      { event_id: "ssc_cgl_result_2027", date: "2027-08-08T18:00:00+05:30", status: "upcoming", predicted_peak_replicas: 20 },
    ]
    render(<OverviewPage state={state({ schedule })} onNavigate={() => {}} />)

    expect(screen.getByText(/SSC CGL results 2027/)).toBeInTheDocument()
  })
})
