import { motion } from "framer-motion"
import { ArrowRight, CalendarClock, FlaskConical } from "lucide-react"
import AnimatedNumber from "../components/AnimatedNumber"
import PredictionRamp from "../components/charts/PredictionRamp"
import { describeComparison } from "../lib/comparison"
import { describeNow, eventName } from "../lib/narrative"
import { term } from "../lib/terms"

const TONE = {
  good: "border-green/40 bg-green/10",
  info: "border-steel/40 bg-steel/10",
  bad: "border-danger/40 bg-danger/10",
  neutral: "border-border bg-panel-raised/70",
}

function Tile({ value, label, hint }) {
  return (
    <div className="rounded-2xl border border-border bg-panel-raised/70 px-5 py-4">
      <div className="text-[34px] font-extrabold leading-none text-text">{value}</div>
      <div className="mt-2 text-[13px] font-medium text-text-muted">{label}</div>
      {hint && <div className="mt-0.5 text-[11.5px] text-text-faint">{hint}</div>}
    </div>
  )
}

function pageLoad(probe, technical) {
  if (!probe?.enabled) return "test visitor off"
  if (!probe.ok || probe.latency_ms == null) return "—"
  return technical ? `${Math.round(probe.latency_ms)} ms` : `${(probe.latency_ms / 1000).toFixed(2)} s`
}

export default function OverviewPage({ state, technical = false, onNavigate }) {
  const now = describeNow(state, technical)
  const summary = state.summary ?? {}
  const result = describeComparison(state.modules?.d?.comparison, technical)
  const next = (state.schedule ?? []).find((row) => row.status === "upcoming")

  return (
    <div className="space-y-5">
      <motion.section
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-3xl border p-6 sm:p-8 ${TONE[now.tone] ?? TONE.neutral}`}
      >
        <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">Right now</div>
        <h2 className="mt-2 text-3xl font-bold leading-tight text-text sm:text-4xl">{now.headline}</h2>
        <p className="mt-3 max-w-3xl text-[16px] leading-relaxed text-text-muted">{now.detail}</p>
      </motion.section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Tile
          value={<AnimatedNumber value={summary.replicas_ready ?? null} />}
          label={`${term("replicas", technical)} ready`}
          hint="each one can serve about 4,000 page loads a minute"
        />
        <Tile
          value={pageLoad(state.probe, technical)}
          label={technical ? "probe latency" : "page load right now"}
          hint={technical ? "dashboard's own request" : "measured by the dashboard's test visitor"}
        />
        <Tile
          value={<span className="text-[24px]">{summary.last_source ? term(summary.last_source, technical) : "—"}</span>}
          label="last change made by"
          hint="who added or removed servers most recently"
        />
      </div>

      <PredictionRamp prediction={state.prediction} currentReplicas={summary.replicas_ready} technical={technical} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-border bg-panel-raised/70 p-5">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            <CalendarClock size={13} aria-hidden="true" /> Next event in the calendar
          </div>
          {next ? (
            <p className="mt-2 text-[15px] text-text">
              <b>{eventName(next.event_id)}</b> on{" "}
              {new Date(next.date).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}
              {next.predicted_peak_replicas != null &&
                ` — CASPER plans ${next.predicted_peak_replicas} ${term("replicas", technical)}.`}
            </p>
          ) : (
            <p className="mt-2 text-[15px] text-text-muted">No upcoming events in the dataset — every recorded event has passed.</p>
          )}
          <button
            type="button"
            onClick={() => onNavigate("schedule")}
            className="mt-3 flex items-center gap-1 text-[13px] font-medium text-steel hover:underline"
          >
            Full schedule <ArrowRight size={13} aria-hidden="true" />
          </button>
        </section>

        <section className="rounded-2xl border border-border bg-panel-raised/70 p-5">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-text-faint">
            <FlaskConical size={13} aria-hidden="true" /> Does planning ahead work?
          </div>
          <p className="mt-2 text-[15px] text-text">
            {result ? result.headline + "." : "Not measured yet — run the experiment to find out."}
          </p>
          <button
            type="button"
            onClick={() => onNavigate("experiment")}
            className="mt-3 flex items-center gap-1 text-[13px] font-medium text-steel hover:underline"
          >
            See the experiment <ArrowRight size={13} aria-hidden="true" />
          </button>
        </section>
      </div>
    </div>
  )
}
