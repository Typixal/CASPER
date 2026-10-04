import { describe, expect, it } from "vitest"
import { term } from "./terms"

describe("term", () => {
  it("speaks plainly by default", () => {
    expect(term("replicas")).toBe("servers")
  })

  it("uses the engineering word when technical mode is on", () => {
    expect(term("replicas", true)).toBe("replicas")
  })

  it("explains p95 in plain words", () => {
    expect(term("p95")).toBe("slowest page loads")
    expect(term("p95", true)).toBe("p95 latency")
  })

  it("fails loudly on an unknown key instead of rendering a blank", () => {
    // A typo in a key would otherwise show an empty label on the projector.
    expect(() => term("replcias")).toThrow(/unknown term/)
  })
})
