import { sourceColor, sourceLabel } from "../../lib/format"

const ORDER = ["predictive", "reactive", "manual"]

/**
 * Stacked horizontal bar showing the predictive/reactive/manual split of
 * every scale action ever logged. Chosen over a donut: no arc-angle math to
 * get pixel-right by hand, reads faster at a glance, and labels sit inline
 * instead of needing a separate legend.
 */
export default function SourceSplitBar({ scaleLog }) {
  const total = scaleLog?.total ?? 0
  const bySource = scaleLog?.by_source ?? {}

  if (!total) {
    return <div className="text-sm text-text-muted">No scale actions logged yet.</div>
  }

  const segments = ORDER.map((key) => ({
    key,
    count: bySource[key] ?? 0,
    pct: ((bySource[key] ?? 0) / total) * 100,
    color: sourceColor(key),
  })).filter((s) => s.count > 0)

  return (
    <div>
      <div className="flex h-8 w-full overflow-hidden rounded-lg border border-border">
        {segments.map((s) => (
          <div
            key={s.key}
            style={{ width: `${s.pct}%`, background: s.color.fill }}
            title={`${sourceLabel(s.key)}: ${s.count}`}
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        {segments.map((s) => (
          <span key={s.key} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color.fill }} />
            <span className="text-text-muted">{sourceLabel(s.key)}</span>
            <span className="font-semibold text-navy">{s.count}</span>
          </span>
        ))}
      </div>
    </div>
  )
}
