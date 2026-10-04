import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import App from "./App"

// jsdom has no EventSource; the app's live connection is irrelevant to
// navigation, so a silent stand-in is enough.
class SilentEventSource {
  close() {}
}

beforeEach(() => {
  vi.stubGlobal("EventSource", SilentEventSource)
  window.location.hash = ""
  localStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("App", () => {
  it("opens on the Overview page", () => {
    render(<App />)

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page")
  })

  it("opens the page named in the URL, so a refresh keeps your place", () => {
    window.location.hash = "#schedule"
    render(<App />)

    expect(screen.getByRole("heading", { level: 1, name: "Event schedule" })).toBeInTheDocument()
  })

  it("switches page from the sidebar and records it in the URL", async () => {
    render(<App />)

    await userEvent.click(screen.getByRole("link", { name: "How it works" }))

    expect(screen.getByRole("heading", { level: 1, name: "How CASPER works" })).toBeInTheDocument()
    expect(window.location.hash).toBe("#how")
  })

  it("ignores an unknown page in the URL and shows the Overview", () => {
    window.location.hash = "#nonsense"
    render(<App />)

    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page")
  })

  it("remembers the technical-terms switch across reloads", async () => {
    const { unmount } = render(<App />)
    await userEvent.click(screen.getByRole("switch", { name: /technical terms/i }))
    unmount()

    render(<App />)

    expect(screen.getByRole("switch", { name: /technical terms/i })).toHaveAttribute("aria-checked", "true")
  })

  it("still works when the browser blocks storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked")
    })

    render(<App />)

    expect(screen.getByRole("switch", { name: /technical terms/i })).toHaveAttribute("aria-checked", "false")
    vi.restoreAllMocks()
  })
})
