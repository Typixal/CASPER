import { describe, expect, it } from "vitest"
import { describeNow, eventName } from "./narrative"

const live = (overrides = {}) => ({
  generated_at: "2026-10-04T12:00:00+00:00",
  docker: { available: true, replicas: [] },
  summary: { replicas_ready: 2, replicas_total: 2 },
  prediction: { exists: false },
  ...overrides,
})

const predicting = (phase, extra = {}) =>
  live({
    summary: { replicas_ready: 4, replicas_total: 4 },
    prediction: {
      exists: true,
      event_id: "cbse_class12_2026",
      phase,
      peak_replicas: 4,
      seconds_to_next: 49,
      ...extra,
    },
  })

describe("eventName", () => {
  it("turns an event id into something a person would say", () => {
    expect(eventName("cbse_class12_2026")).toBe("CBSE Class 12 results 2026")
    expect(eventName("kerala_plustwo_admission_2026")).toBe("Kerala Plus Two admissions 2026")
    expect(eventName("ssc_cgl_result_2026")).toBe("SSC CGL results 2026")
  })

  it("falls back to a tidied id for anything it does not recognise", () => {
    expect(eventName("some_new_event_2027")).toBe("Some New Event 2027")
  })
})

describe("describeNow", () => {
  it("says it is connecting before the first snapshot arrives", () => {
    expect(describeNow({ starting: true }).headline).toMatch(/connecting/i)
  })

  it("explains an offline portal without jargon", () => {
    const now = describeNow(live({ docker: { available: false, error: "npipe ..." } }))

    expect(now.tone).toBe("bad")
    expect(now.headline).toMatch(/offline/i)
    expect(now.detail).not.toMatch(/npipe|docker api/i) // raw errors stay in technical views
  })

  it("describes an idle portal when nothing is scheduled", () => {
    const now = describeNow(live())

    expect(now.headline).toMatch(/no event/i)
    expect(now.detail).toMatch(/2 servers/)
  })

  it("before the event, says CASPER is getting ready and when", () => {
    const now = describeNow(predicting("before"))

    expect(now.headline).toMatch(/getting ready for CBSE Class 12 results 2026/)
    expect(now.detail).toMatch(/49 seconds/)
    expect(now.detail).toMatch(/before students arrive/)
  })

  it("during the rush, points out the servers were ready in advance", () => {
    const now = describeNow(predicting("ramp"))

    expect(now.tone).toBe("good")
    expect(now.headline).toMatch(/students are arriving/i)
    expect(now.detail).toMatch(/4 servers/)
  })

  it("after the event, says it is winding down to save money", () => {
    const now = describeNow(predicting("after"))

    expect(now.headline).toMatch(/is over/)
    expect(now.detail).toMatch(/save/)
  })

  it("switches to engineering words in technical mode", () => {
    const now = describeNow(predicting("ramp"), true)

    expect(now.detail).toMatch(/4 replicas/)
  })
})
