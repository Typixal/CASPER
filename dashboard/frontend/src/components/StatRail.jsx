import { motion } from "framer-motion"
import { Gauge, ListChecks, Network, Server, Timer } from "lucide-react"
import AnimatedNumber from "./AnimatedNumber"
import { sourceColor, sourceLabel, timeOnly } from "../lib/format"

function StatTile({ icon: Icon, label, value, sub, accent = "text-text", index = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.05 + index * 0.05, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-2xl border border-border bg-panel-raised/70 px-4 py-3.5 backdrop-blur-sm"
    >
      <div className="flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-text-faint">
        <Icon size={12} strokeWidth={2.4} />
        {label}
      </div>
      <div className={`mt-1.5 text-[34px] font-extrabold leading-none ${accent}`}>{value}</div>
      <div className="mt-1 truncate text-[11px] text-text-faint">{sub ?? " "}</div>
    </motion.div>
  )
}

export default function StatRail({ state }) {
  const summary = state.summary ?? {}
  const probe = state.probe ?? {}
  const scaleLog = state.scale_log ?? {}
  const lastColor = summary.last_source ? sourceColor(summary.last_source) : null

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatTile
        index={0}
        icon={Server}
        label="replicas ready"
        value={<AnimatedNumber value={summary.replicas_ready ?? null} />}
        sub={`of ${summary.replicas_total ?? 0} containers`}
        accent="text-green"
      />
      <StatTile
        index={1}
        icon={Network}
        label="routed by nginx"
        value={<AnimatedNumber value={summary.drained ? 0 : (summary.replicas_routed ?? null)} />}
        sub={summary.drained ? "drained — nginx returns 502" : "upstream servers"}
        accent={summary.drained ? "text-danger" : "text-steel"}
      />
      <StatTile
        index={2}
        icon={Gauge}
        label="last scaled by"
        value={
          <span className="text-[26px]">
            {summary.last_source ? sourceLabel(summary.last_source) : "—"}
          </span>
        }
        sub={scaleLog.last ? timeOnly(scaleLog.last.timestamp) : " "}
        accent={lastColor?.text ?? "text-text"}
      />
      <StatTile
        index={3}
        icon={Timer}
        label="probe latency"
        value={
          probe.ok ? (
            <>
              <AnimatedNumber value={probe.latency_ms ? Math.round(probe.latency_ms) : null} />
              <span className="ml-1 text-lg font-semibold text-text-faint">ms</span>
            </>
          ) : probe.enabled ? (
            <span className="text-[26px] text-danger">{probe.error ? "error" : "—"}</span>
          ) : (
            <span className="text-[26px] text-text-faint">off</span>
          )
        }
        sub="dashboard probe, not k6"
      />
      <StatTile
        index={4}
        icon={ListChecks}
        label="scale actions"
        value={<AnimatedNumber value={scaleLog.total ?? null} />}
        sub="in the audit log"
      />
    </div>
  )
}
