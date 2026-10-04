import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import ReplicaGrid from "./ReplicaGrid"

const docker = {
  available: true,
  replicas: [
    { name: "casper-module-c-portal-1", short_name: "1", id: "2699e2552c3f", state: "running", health: "healthy", ready: true, routed: true },
    { name: "casper-module-c-portal-2", short_name: "2", id: "18843eda2c59", state: "running", health: "starting", ready: false, routed: false },
  ],
}
const probeSummary = { per_replica: { "2699e2552c3f": 7 } }

describe("ReplicaGrid", () => {
  it("names each server plainly and says whether it is getting visitors", () => {
    render(<ReplicaGrid docker={docker} probeSummary={probeSummary} />)

    expect(screen.getByText("server 1")).toBeInTheDocument()
    expect(screen.getByText("receiving visitors")).toBeInTheDocument()
    expect(screen.getByText("not receiving visitors yet")).toBeInTheDocument()
  })

  it("hides container ids in plain mode", () => {
    render(<ReplicaGrid docker={docker} probeSummary={probeSummary} />)

    expect(screen.queryByText("2699e2552c3f")).not.toBeInTheDocument()
    expect(screen.getByText(/7 test visits/)).toBeInTheDocument()
  })

  it("shows container ids and nginx wording in technical mode", () => {
    render(<ReplicaGrid docker={docker} probeSummary={probeSummary} technical />)

    expect(screen.getByText("portal-1")).toBeInTheDocument()
    expect(screen.getByText("2699e2552c3f")).toBeInTheDocument()
    expect(screen.getByText("in nginx upstream")).toBeInTheDocument()
  })
})
