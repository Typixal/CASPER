// Formatting helpers shared by the panels. Dependency-free on purpose.

/**
 * @param {string} iso ISO timestamp.
 * @returns {string} Locale time string, or an em dash when missing/invalid.
 */
export function timeOnly(iso) {
  if (!iso) return "—"
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString()
}

/**
 * @param {number|null} seconds
 * @returns {string} Compact duration such as "45s" or "2m 5s".
 */
export function countdown(seconds) {
  if (seconds === null || seconds === undefined) return "—"
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

/**
 * Seconds from `iso` to `referenceIso` (or now). Pass the snapshot's
 * generated_at to follow the server clock instead of the browser's.
 * @param {string} iso
 * @param {string} [referenceIso]
 * @returns {number|null} Null for an invalid timestamp.
 */
export function secondsSince(iso, referenceIso) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  const ref = referenceIso ? new Date(referenceIso) : new Date()
  return (ref.getTime() - d.getTime()) / 1000
}

/**
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number} value limited to [min, max].
 */
export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

const SOURCE_LABEL = {
  predictive: "predictive",
  reactive: "reactive",
  manual: "manual",
}

/**
 * @param {string} source "predictive" | "reactive" | "manual".
 * @returns {string} Display label.
 */
export function sourceLabel(source) {
  return SOURCE_LABEL[source] ?? source ?? "unknown"
}

// One colour per source for every chart and badge. Brighter than the
// architecture diagram's originals, which are too dim on the dark theme.
export const SOURCE_COLORS = {
  predictive: { text: "text-steel", bg: "bg-steel", fill: "#6E9BE0" },
  reactive: { text: "text-amber", bg: "bg-amber", fill: "#F7A84F" },
  manual: { text: "text-text-muted", bg: "bg-text-muted", fill: "#94A2C4" },
}

/**
 * @param {string} source
 * @returns {object} The SOURCE_COLORS entry, manual for unknown sources.
 */
export function sourceColor(source) {
  return SOURCE_COLORS[source] ?? SOURCE_COLORS.manual
}
