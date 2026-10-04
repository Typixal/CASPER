import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import StatRail from "./StatRail"

const state = {
  summary: { replicas_ready: 2, replicas_total: 2, replicas_routed: 2, drained: false, last_source: "manual" },
  probe: { enabled: true, ok: true, latency_ms: 80 },
  scale_log: { total: 42, last: { timestamp: "2026-10-04T12:00:00+00:00" } },
}

describe("StatRail", () => {
  it("labels its tiles in plain words by default", () => {
    render(<StatRail state={state} />)

    for (const label of ["servers ready", "receiving visitors", "last changed by", "page load right now", "changes recorded"]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    expect(screen.queryByText(/nginx|probe|k6/i)).not.toBeInTheDocument()
  })

  it("shows who made the last change in plain words", () => {
    render(<StatRail state={state} />)

    expect(screen.getByText("by hand")).toBeInTheDocument()
  })

  it("keeps the engineering labels in technical mode", () => {
    render(<StatRail state={state} technical />)

    expect(screen.getByText("routed by nginx")).toBeInTheDocument()
    expect(screen.getByText("probe latency")).toBeInTheDocument()
  })
})
