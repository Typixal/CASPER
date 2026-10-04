import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import SchedulePage from "./SchedulePage"

// Shaped like collector.read_schedule().
const rows = [
  {
    event_id: "cbse_class12_2026",
    board: "CBSE",
    event_type: "exam_result",
    date: "2026-05-13T10:00:00+05:30",
    registered_candidates: 1650000,
    predicted_peak_replicas: 13,
    ramp_start: "2026-05-13T09:30:00+05:30",
    ramp_end: "2026-05-13T14:00:00+05:30",
    status: "past",
    demo: true,
  },
  {
    event_id: "ssc_cgl_result_2027",
    board: "SSC",
    event_type: "recruitment_result",
    date: "2027-08-08T18:00:00+05:30",
    registered_candidates: 2650000,
    predicted_peak_replicas: null,
    ramp_start: null,
    ramp_end: null,
    status: "upcoming",
    demo: false,
  },
]

const rowFor = (name) => screen.getByText(name).closest("li")

describe("SchedulePage", () => {
  it("lists every event by a name a person would recognise", () => {
    render(<SchedulePage schedule={rows} />)

    expect(screen.getByText("CBSE Class 12 results 2026")).toBeInTheDocument()
    expect(screen.getByText("SSC CGL results 2027")).toBeInTheDocument()
  })

  it("shows how many students and how many servers CASPER plans", () => {
    render(<SchedulePage schedule={rows} />)
    const cbse = within(rowFor("CBSE Class 12 results 2026"))

    expect(cbse.getByText(/1,650,000 students registered/)).toBeInTheDocument()
    expect(cbse.getByText(/13 servers/)).toBeInTheDocument()
  })

  it("says plainly when there is no forecast yet", () => {
    render(<SchedulePage schedule={rows} />)

    expect(within(rowFor("SSC CGL results 2027")).getByText(/no forecast yet/i)).toBeInTheDocument()
  })

  it("marks events as past or upcoming", () => {
    render(<SchedulePage schedule={rows} />)

    expect(within(rowFor("CBSE Class 12 results 2026")).getByText("past")).toBeInTheDocument()
    expect(within(rowFor("SSC CGL results 2027")).getByText("upcoming")).toBeInTheDocument()
  })

  it("highlights the event the live demo is replaying", () => {
    render(<SchedulePage schedule={rows} />)

    expect(within(rowFor("CBSE Class 12 results 2026")).getByText(/replaying in the demo/i)).toBeInTheDocument()
  })

  it("uses replica wording in technical mode", () => {
    render(<SchedulePage schedule={rows} technical />)

    expect(within(rowFor("CBSE Class 12 results 2026")).getByText(/13 replicas/)).toBeInTheDocument()
  })

  it("explains an empty schedule instead of showing a blank page", () => {
    render(<SchedulePage schedule={[]} />)

    expect(screen.getByText(/no events/i)).toBeInTheDocument()
  })
})
