import { motion } from "framer-motion"
import { AlertCircle, CalendarClock, Flame, MoveDown, MoveUp, ShieldCheck, Timer } from "lucide-react"
import AnimatedNumber from "../AnimatedNumber"
import { clamp, timeOnly } from "../../lib/format"

const PHASE = {
  before: {
    label: "before ramp",
    blurb: "capacity provisioned ahead of traffic",
    icon: CalendarClock,
    text: "text-text-muted",
    ring: "border-border-bright bg-panel",
    bar: "#5D6B8F",
    glow: "rgba(93,107,143,0.25)",
  },
  ramp: {
    label: "inside event window",
    blurb: "traffic climbing — capacity already in place",
    icon: MoveUp,
    text: "text-steel",
    ring: "border-steel/50 bg-steel/10",
    bar: "#6E9BE0",
    glow: "rgba(110,155,224,0.35)",
  },
  peak: {
    label: "past predicted peak",
    blurb: "holding peak capacity through the event",
    icon: Flame,
    text: "text-amber",
    ring: "border-amber/50 bg-amber/10",
    bar: "#F7A84F",
    glow: "rgba(247,168,79,0.35)",
  },
  after: {
    label: "window closed",
    blurb: "event handled — draining back down",
    icon: ShieldCheck,
    text: "text-green",
    ring: "border-green/50 bg-green/10",
    bar: "#3FC98D",
    glow: "rgba(63,201,141,0.3)",
  },
}

// mm:ss for anything under an hour — reads faster on a projector than "93s".
function bigCountdown(seconds) {
  if (seconds === null || seconds === undefined) return { value: "—", unit: "" }
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return { value: String(s), unit: "sec" }
  const m = Math.floor(s / 60)
  const rem = s % 60
  return { value: `${m}:${String(rem).padStart(2, "0")}`, unit: "min" }
}

function peakPercent(start, peak, end) {
  const s = new Date(start).getTime()
  const p = new Date(peak).getTime()
  const e = new Date(end).getTime()
  if (![s, p, e].every(Number.isFinite) || e === s) return 50
  return clamp(((p - s) / (e - s)) * 100, 0, 100)
}

function Shell({ children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-3xl border border-border bg-panel-raised/70 p-6 shadow-[0_8px_40px_-20px_rgba(0,0,0,1)] backdrop-blur-sm sm:p-7"
    >
      {children}
    </motion.section>
  )
}

export default function PredictionRamp({ prediction, currentReplicas }) {
  if (!prediction?.exists) {
    return (
      <Shell>
        <div className="flex items-center justify-center gap-3 py-8 text-text-muted">
          <CalendarClock size={18} />
          No active Prediction — the predictive policy has nothing scheduled.
        </div>
      </Shell>
    )
  }

  if (prediction.error) {
    return (
      <Shell>
        <div className="flex items-center justify-center gap-3 py-8 text-danger">
          <AlertCircle size={18} />
          {prediction.error}
        </div>
      </Shell>
    )
  }

  const phase = PHASE[prediction.phase] ?? PHASE.before
  const PhaseIcon = phase.icon
  const progress = clamp(prediction.progress_pct ?? 0, 0, 100)
  const peakPct = peakPercent(prediction.ramp_start, prediction.ramp_peak, prediction.ramp_end)
  const { value, unit } = bigCountdown(prediction.seconds_to_next)
  const scalingUp = (prediction.next_action ?? "").toLowerCase().includes("up")

  return (
    <Shell>
      <div className="flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider ${phase.ring} ${phase.text}`}>
              <PhaseIcon size={13} strokeWidth={2.5} />
              {prediction.phase}
            </span>
            <span className="font-mono text-xs text-text-faint">{prediction.event_id}</span>
            <span className="rounded-full border border-border bg-panel px-2 py-0.5 text-[10.5px] text-text-faint">
              {prediction.kind}
            </span>
          </div>

          <div className="mt-3 flex items-baseline gap-3">
            <span className="flex items-center gap-2 text-2xl font-bold text-text sm:text-[28px]">
              {scalingUp ? (
                <MoveUp size={24} className="text-steel" strokeWidth={2.6} />
              ) : (
                <MoveDown size={24} className="text-green" strokeWidth={2.6} />
              )}
              {prediction.next_action ?? "on schedule"}
            </span>
          </div>
          <p className="mt-1.5 text-sm text-text-muted">{phase.blurb}</p>
        </div>

        {/* Countdown — the single biggest number on the page */}
        <div className="flex items-center gap-6">
          <div className="text-right">
            <div className="flex items-center justify-end gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-text-faint">
              <Timer size={12} strokeWidth={2.4} />
              next action in
            </div>
            <div className="tnum mt-0.5 text-5xl font-extrabold leading-none text-text sm:text-6xl">
              {value}
              <span className="ml-1.5 text-lg font-semibold text-text-faint">{unit}</span>
            </div>
          </div>

          <div className="h-14 w-px bg-border" />

          <div className="text-right">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-text-faint">
              predicted peak
            </div>
            <div className="mt-0.5 text-5xl font-extrabold leading-none text-steel sm:text-6xl">
              <AnimatedNumber value={prediction.peak_replicas} />
            </div>
            <div className="mt-0.5 text-[11px] text-text-faint">
              now running <span className="tnum font-semibold text-text-muted">{currentReplicas ?? 0}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Ramp bar */}
      <div className="mt-7">
        <div className="relative h-2.5 overflow-visible rounded-full border border-border bg-panel/80">
          {/* Ghost of the window that has not started yet, so "before" does
              not render as an empty grey track with nothing on it. */}
          {prediction.phase === "before" && (
            <div
              className="absolute inset-0 rounded-full opacity-30"
              style={{
                background:
                  "repeating-linear-gradient(115deg, #33456E 0 8px, transparent 8px 16px)",
              }}
            />
          )}

          <motion.div
            className="relative h-2.5 rounded-full"
            style={{ background: phase.bar, boxShadow: `0 0 18px ${phase.glow}` }}
            initial={false}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
          />

          {/* predicted-peak tick */}
          <div
            className="absolute top-1/2 h-4 w-0.5 -translate-y-1/2 rounded bg-text-faint"
            style={{ left: `${peakPct}%` }}
            title={`predicted peak ${timeOnly(prediction.ramp_peak)}`}
          />

          {/* "now" needle, only while inside the window */}
          {prediction.phase !== "before" && prediction.phase !== "after" && (
            <motion.div
              className="absolute -top-1 h-4.5 w-1 -translate-x-1/2 rounded-full bg-text"
              initial={false}
              animate={{ left: `${progress}%` }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              title="now"
            />
          )}
        </div>

        <div className="mt-2.5 flex justify-between font-mono text-[11px] text-text-faint">
          <span>ramp_start {timeOnly(prediction.ramp_start)}</span>
          <span>peak {timeOnly(prediction.ramp_peak)}</span>
          <span>ramp_end {timeOnly(prediction.ramp_end)}</span>
        </div>
      </div>
    </Shell>
  )
}
