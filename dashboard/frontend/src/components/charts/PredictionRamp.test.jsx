import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import PredictionRamp from "./PredictionRamp"

const prediction = {
  exists: true,
  event_id: "cbse_class12_2026",
  kind: "demo (time-shifted)",
  phase: "before",
  peak_replicas: 4,
  progress_pct: 0,
  seconds_to_next: 49,
  next_action: "scale UP to 4",
  ramp_start: "2026-10-04T09:30:00+05:30",
  ramp_peak: "2026-10-04T10:15:00+05:30",
  ramp_end: "2026-10-04T14:00:00+05:30",
}

describe("PredictionRamp", () => {
  it("labels the timeline in plain words by default", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText(/get ready/)).toBeInTheDocument()
    expect(screen.getByText(/wind down/)).toBeInTheDocument()
    expect(screen.queryByText(/ramp_start/)).not.toBeInTheDocument()
  })

  it("uses the schema field names in technical mode", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} technical />)

    expect(screen.getByText(/ramp_start/)).toBeInTheDocument()
  })

  it("names the event, not its id, in plain mode", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText("CBSE Class 12 results 2026")).toBeInTheDocument()
  })
})

describe("PredictionRamp actions", () => {
  it("describes the next step in plain words", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText(/add servers \(up to 4\)/i)).toBeInTheDocument()
    expect(screen.queryByText(/scale UP/)).not.toBeInTheDocument()
  })

  it("describes winding down in plain words", () => {
    render(<PredictionRamp prediction={{ ...prediction, phase: "ramp", next_action: "scale DOWN" }} currentReplicas={4} />)

    expect(screen.getByText(/remove the extra servers/i)).toBeInTheDocument()
  })
})

describe("PredictionRamp labels", () => {
  it("labels its numbers in plain words", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText(/next step in/i)).toBeInTheDocument()
    expect(screen.getByText(/planned for the rush/i)).toBeInTheDocument()
    expect(screen.queryByText(/next action in/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/predicted peak/i)).not.toBeInTheDocument()
  })

  it("names the phase in plain words", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText("getting ready")).toBeInTheDocument()
  })

  it("calls the time-shifted copy a demo replay", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} />)

    expect(screen.getByText("demo replay")).toBeInTheDocument()
    expect(screen.queryByText(/time-shifted/)).not.toBeInTheDocument()
  })

  it("keeps the technical labels in technical mode", () => {
    render(<PredictionRamp prediction={prediction} currentReplicas={2} technical />)

    expect(screen.getByText(/next action in/i)).toBeInTheDocument()
    expect(screen.getByText(/predicted peak/i)).toBeInTheDocument()
    expect(screen.getByText("before")).toBeInTheDocument()
  })
})
