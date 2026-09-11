import { sourceColor, sourceLabel, timeOnly } from "../lib/format"

function StatTile({ label, value, sub, accent }) {
  return (
    <div className="rounded-xl border border-border bg-panel-raised p-4 shadow-sm">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className={`mt-1 text-3xl font-bold leading-tight ${accent ?? "text-navy"}`}>
        {value}
      </div>
      <div className="mt-0.5 text-xs text-text-muted">{sub ?? " "}</div>
    </div>
  )
}

export default function StatRail({ state }) {
  const summary = state.summary ?? {}
  const probe = state.probe ?? {}
  const scaleLog = state.scale_log ?? {}
  const lastSourceColor = summary.last_source ? sourceColor(summary.last_source) : null

  return (
    <section className="grid grid-cols-2 gap-3 px-4 pt-6 sm:grid-cols-3 sm:px-6 lg:grid-cols-5">
      <StatTile
        label="Replicas ready"
        value={summary.replicas_ready ?? "—"}
        sub={`of ${summary.replicas_total ?? 0} containers`}
      />
      <StatTile
        label="Routed by nginx"
        value={summary.drained ? "0" : (summary.replicas_routed ?? "—")}
        sub={summary.drained ? "drained — 502" : "upstream servers"}
        accent={summary.drained ? "text-danger" : undefined}
      />
      <StatTile
        label="Last scaled by"
        value={summary.last_source ? sourceLabel(summary.last_source) : "—"}
        sub={scaleLog.last ? timeOnly(scaleLog.last.timestamp) : " "}
        accent={lastSourceColor?.text}
      />
      <StatTile
        label="Probe latency"
        value={probe.ok ? `${probe.latency_ms} ms` : probe.enabled ? (probe.error ? "err" : "—") : "off"}
        sub="dashboard probe, not k6"
      />
      <StatTile
        label="Scale actions"
        value={scaleLog.total ?? "—"}
        sub="in audit log"
      />
    </section>
  )
}
