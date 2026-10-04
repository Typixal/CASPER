// Plain-English description of what the system is doing right now.
//
// The Overview page leads with this so a non-technical viewer gets the story
// in one sentence before seeing any chart. Pure functions over the snapshot
// the backend streams, so every situation the demo can be in is unit-tested.

import { term } from "./terms"

// Readable names for the event families in Module A's dataset. Anything not
// listed falls back to a tidied version of its id.
const KNOWN_EVENTS = {
  cbse_class12: "CBSE Class 12 results",
  kerala_plustwo_admission: "Kerala Plus Two admissions",
  ssc_cgl_result: "SSC CGL results",
}

export function eventName(eventId) {
  if (!eventId) return "the event"
  const match = eventId.match(/^(.*)_(\d{4})$/)
  const [stem, year] = match ? [match[1], match[2]] : [eventId, null]

  const name =
    KNOWN_EVENTS[stem] ??
    stem
      .split("_")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ")
  return year ? `${name} ${year}` : name
}

export function humanDuration(seconds) {
  if (seconds === null || seconds === undefined) return "a moment"
  const s = Math.max(0, Math.round(seconds))
  if (s < 90) return `${s} seconds`
  const m = Math.round(s / 60)
  if (m < 90) return `${m} minutes`
  return `${Math.round(m / 60)} hours`
}

export function describeNow(state, technical = false) {
  const servers = term("replicas", technical)

  if (state?.starting) {
    return { tone: "neutral", headline: "Connecting to CASPER…", detail: "Waiting for the first update from the system." }
  }
  if (state?.fatal_error) {
    return { tone: "bad", headline: "The dashboard hit an error", detail: "Switch on technical terms to see the details." }
  }
  if (state?.docker && !state.docker.available) {
    return {
      tone: "bad",
      headline: "The portal is offline",
      detail: `No ${servers} are running right now, so there is nothing to scale. Start the demo to bring the portal up.`,
    }
  }

  const ready = state?.summary?.replicas_ready ?? 0
  const p = state?.prediction
  if (!p?.exists) {
    return {
      tone: "neutral",
      headline: "No event is scheduled",
      detail: `The portal is idling on ${ready} ${servers}, waiting for the next exam result or deadline.`,
    }
  }

  const name = eventName(p.event_id)
  switch (p.phase) {
    case "before":
      return {
        tone: "info",
        headline: `CASPER is getting ready for ${name}`,
        detail: `It will add ${servers} in ${humanDuration(p.seconds_to_next)}, before students arrive, planning for ${p.peak_replicas} at the busiest moment.`,
      }
    case "ramp":
    case "peak":
      return {
        tone: "good",
        headline: "Students are arriving",
        detail: `${ready} ${servers} were already running before the rush started, so pages keep loading quickly.`,
      }
    case "after":
      return {
        tone: "neutral",
        headline: `${name} is over`,
        detail: `CASPER is winding back down to save money on ${servers} nobody needs any more.`,
      }
    default:
      return { tone: "neutral", headline: name, detail: `${ready} ${servers} running.` }
  }
}
