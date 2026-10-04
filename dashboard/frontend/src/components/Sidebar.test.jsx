import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { PAGES } from "../lib/pages"
import Sidebar from "./Sidebar"

function renderSidebar(props = {}) {
  const handlers = { onNavigate: vi.fn(), onToggleTechnical: vi.fn() }
  render(<Sidebar page="overview" technical={false} connected {...handlers} {...props} />)
  return handlers
}

describe("Sidebar", () => {
  it("lists the five pages, story first", () => {
    renderSidebar()

    const labels = screen.getAllByRole("link").map((a) => a.textContent)
    expect(labels).toEqual(["Overview", "Event schedule", "Live system", "Experiment", "How it works"])
    expect(PAGES.map((p) => p.id)).toEqual(["overview", "schedule", "live", "experiment", "how"])
  })

  it("marks the current page for screen readers and styling", () => {
    renderSidebar({ page: "experiment" })

    expect(screen.getByRole("link", { name: "Experiment" })).toHaveAttribute("aria-current", "page")
    expect(screen.getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current")
  })

  it("navigates when a page is clicked", async () => {
    const { onNavigate } = renderSidebar()

    await userEvent.click(screen.getByRole("link", { name: "Event schedule" }))

    expect(onNavigate).toHaveBeenCalledWith("schedule")
  })

  it("has a switch for technical terms that reflects its state", async () => {
    const { onToggleTechnical } = renderSidebar({ technical: true })

    const toggle = screen.getByRole("switch", { name: /technical terms/i })
    expect(toggle).toHaveAttribute("aria-checked", "true")

    await userEvent.click(toggle)
    expect(onToggleTechnical).toHaveBeenCalled()
  })

  it("shows whether the dashboard is receiving live updates", () => {
    renderSidebar({ connected: false })

    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })
})
