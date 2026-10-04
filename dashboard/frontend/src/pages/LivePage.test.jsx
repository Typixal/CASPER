import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import LivePage from "./LivePage"

const state = {
  generated_at: "2026-10-04T12:00:00+00:00",
  docker: { available: true, replicas: [{ name: "casper-module-c-portal-1", short_name: "1", id: "abc123def456", state: "running", health: "healthy", ready: true, routed: true }] },
  summary: { replicas_ready: 1, replicas_total: 1, replicas_routed: 1, drained: false, last_source: "manual" },
  nginx: { exists: true, servers: ["casper-module-c-portal-1:5000"], drained: false, modified: null, error: null },
  scale_log: { exists: true, actions: [], total: 0, by_source: {}, last: null },
  probe: { enabled: true, ok: true, latency_ms: 80 },
  probe_summary: { history: [], samples: 0, per_replica: {}, avg_ms: null, max_ms: null, error_count: 0 },
}

const headings = () => screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)

describe("LivePage", () => {
  it("titles each panel in plain words by default", () => {
    render(<LivePage state={state} />)

    expect(headings()).toEqual([
      "Servers over time",
      "Servers running now",
      "How fast pages load",
      "Who changed the server count",
      "Traffic director",
    ])
  })

  it("titles each panel technically in technical mode", () => {
    render(<LivePage state={state} technical />)

    expect(headings()).toEqual([
      "Capacity over time",
      "Portal replicas",
      "Probe latency",
      "Scaling source split",
      "nginx upstream",
    ])
  })

  it("explains what each panel shows", () => {
    render(<LivePage state={state} />)

    expect(screen.getByText(/each card is one copy of the portal/i)).toBeInTheDocument()
    expect(screen.getByText(/hands each visitor to one of the servers/i)).toBeInTheDocument()
  })
})

describe("LivePage probe control", () => {
  it("lets you switch the dashboard's test visitor off", async () => {
    const onToggleProbe = vi.fn()
    render(<LivePage state={state} onToggleProbe={onToggleProbe} />)

    await userEvent.click(screen.getByRole("button", { name: /test visitor on/i }))

    expect(onToggleProbe).toHaveBeenCalled()
  })

  it("shows the visitor locked off and disables the button during the experiment", () => {
    render(<LivePage state={{ ...state, probe: { enabled: false, locked: true } }} onToggleProbe={() => {}} />)

    expect(screen.getByRole("button", { name: /locked off/i })).toBeDisabled()
  })
})
