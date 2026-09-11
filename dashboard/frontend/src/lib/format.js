// Small formatting helpers shared by every panel. Kept dependency-free
// (no date-fns/etc) since the whole point of this project is a minimal,
// fully-offline build.

export function timeOnly(iso) {
  if (!iso) return "—"
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString()
}

export function countdown(seconds) {
  if (seconds === null || seconds === undefined) return "—"
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

// Seconds elapsed between an ISO timestamp and "now" (or a reference ISO
// timestamp such as generated_at, so charts stay stable relative to the
// server's own clock rather than the browser's).
export function secondsSince(iso, referenceIso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const ref = referenceIso ? new Date(referenceIso) : new Date()
  return (ref.getTime() - d.getTime()) / 1000
}

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

const SOURCE_LABEL = {
  predictive: "predictive",
  reactive: "reactive",
  manual: "manual",
}

export function sourceLabel(source) {
  return SOURCE_LABEL[source] ?? source ?? "unknown"
}

// Tailwind class fragments per source, centralised so every chart/badge
// agrees on the same mapping (steel=predictive, amber=reactive, grey=manual).
export const SOURCE_COLORS = {
  predictive: { text: "text-steel", bg: "bg-steel", fill: "#4A6FA5" },
  reactive: { text: "text-amber", bg: "bg-amber", fill: "#F2994A" },
  manual: { text: "text-text-muted", bg: "bg-text-muted", fill: "#6B7280" },
}

export function sourceColor(source) {
  return SOURCE_COLORS[source] ?? SOURCE_COLORS.manual
}
