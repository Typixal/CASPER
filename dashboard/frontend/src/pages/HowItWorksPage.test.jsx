import { render, screen, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import HowItWorksPage from "./HowItWorksPage"

describe("HowItWorksPage", () => {
  it("walks through the four modules in order, in plain words", () => {
    render(<HowItWorksPage />)

    const steps = screen.getAllByRole("listitem", { name: /^step/i }).map((li) => li.getAttribute("aria-label"))
    expect(steps).toEqual([
      "step 1: Knows the calendar",
      "step 2: Estimates the crowd",
      "step 3: Gets servers ready",
      "step 4: Proves it works",
    ])
  })

  it("states the problem CASPER solves before the solution", () => {
    render(<HowItWorksPage />)

    expect(screen.getByText(/crash on result day/i)).toBeInTheDocument()
  })

  it("has a glossary pairing each plain word with its technical term", () => {
    render(<HowItWorksPage />)

    const glossary = screen.getByRole("table", { name: /glossary/i })
    const serversRow = within(glossary).getByText("servers").closest("tr")
    expect(within(serversRow).getByText("replicas")).toBeInTheDocument()
  })
})
