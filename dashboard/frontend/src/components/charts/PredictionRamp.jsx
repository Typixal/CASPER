import { clamp, countdown, timeOnly } from "../../lib/format"

const PHASE_STYLE = {
  before: { label: "before ramp", chip: "bg-text-faint/20 text-text-muted", fill: "#9AA5C0" },
  ramp: { label: "inside event window", chip: "bg-steel/15 text-steel", fill: "#4A6FA5" },
  peak: { label: "past predicted peak", chip: "bg-amber/15 text-amber", fill: "#F2994A" },
  after: { label: "window closed", chip: "bg-green/15 text-green", fill: "#2F9E6E" },
}

// Where does ramp_peak fall between ramp_start (0%) and ramp_end (100%)?
// Computed client-side from the three ISO timestamps -- no new backend field.
function peakPercent(start, peak, end) {
  const s = new Date(start).getTime()
  const p = new Date(peak).getTime()
  const e = new Date(end).getTime()
  if (![s, p, e].every(Number.isFinite) || e === s) return 50
  return clamp(((p - s) / (e - s)) * 100, 0, 100)
}

export default function PredictionRamp({ prediction }) {
  if (!prediction?.exists) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-panel/60 px-6 py-10 text-center text-text-muted">
        No active Prediction — the predictive policy has nothing scheduled.
      </div>
    )
  }

  if (prediction.error) {
    return (
      <div className="rounded-2xl border border-danger/40 bg-danger-bg px-6 py-6 text-danger">
        {prediction.error}
      </div>
    )
  }

  const phase = PHASE_STYLE[prediction.phase] ?? PHASE_STYLE.before
  const progress = clamp(prediction.progress_pct ?? 0, 0, 100)
  const peakPct = peakPercent(prediction.ramp_start, prediction.ramp_peak, prediction.ramp_end)

  return (
    <div className="rounded-2xl border border-border bg-panel-raised p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            {prediction.kind ?? "prediction"} &middot; <span className="font-mono normal-case">{prediction.event_id}</span>
          </div>
          <div className="mt-1 text-3xl font-bold text-navy sm:text-4xl">
            {prediction.next_action ?? "on schedule"}
          </div>
          <div className="mt-1 text-lg text-text-muted">
            in <span className="font-mono font-semibold text-text">{countdown(prediction.seconds_to_next)}</span>
          </div>
        </div>
        <span className={`shrink-0 rounded-full px-4 py-1.5 text-sm font-semibold ${phase.chip}`}>
          {prediction.phase} &middot; {phase.label}
        </span>
      </div>

      {/* Timeline bar */}
      <div className="relative mt-8 h-3 rounded-full bg-border">
        <div
          className="h-3 rounded-full transition-[width] duration-500"
          style={{ width: `${progress}%`, background: phase.fill }}
        />
        {/* peak tick */}
        <div
          className="absolute top-1/2 h-5 w-0.5 -translate-y-1/2 bg-navy/70"
          style={{ left: `${peakPct}%` }}
          title={`predicted peak: ${timeOnly(prediction.ramp_peak)}`}
        />
        {/* "now" marker, only meaningful while inside the window */}
        {prediction.phase !== "before" && prediction.phase !== "after" && (
          <div
            className="absolute -top-1.5 h-6 w-1 -translate-x-1/2 rounded-full bg-navy shadow"
            style={{ left: `${progress}%` }}
            title="now"
          />
        )}
      </div>

      <div className="mt-2 flex justify-between text-xs text-text-muted">
        <span>start {timeOnly(prediction.ramp_start)}</span>
        <span>peak {timeOnly(prediction.ramp_peak)} &middot; {prediction.peak_replicas} replicas</span>
        <span>end {timeOnly(prediction.ramp_end)}</span>
      </div>

      <div className="mt-4 border-t border-border pt-3 text-xs text-text-muted">
        source: <span className="font-mono">{prediction.file}</span>
      </div>
    </div>
  )
}
