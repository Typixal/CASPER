import { motion } from "framer-motion"
import AnimatedNumber from "../AnimatedNumber"
import { sourceColor, sourceLabel } from "../../lib/format"

const ORDER = ["predictive", "reactive", "manual"]

/**
 * Who has been turning the knob. Once Module D's reactive baseline runs,
 * this is the at-a-glance answer to "which strategy caused what" -- the
 * comparison the whole project exists to make.
 */
export default function SourceSplitBar({ scaleLog }) {
  const total = scaleLog?.total ?? 0
  const bySource = scaleLog?.by_source ?? {}

  const segments = ORDER.map((key) => ({
    key,
    count: bySource[key] ?? 0,
    pct: total ? ((bySource[key] ?? 0) / total) * 100 : 0,
    color: sourceColor(key),
  }))

  if (!total) {
    return <div className="py-6 text-center text-sm text-text-faint">No scale actions logged yet.</div>
  }

  return (
    <div>
      <div className="flex h-9 w-full gap-1 overflow-hidden rounded-xl bg-panel p-1">
        {segments
          .filter((s) => s.count > 0)
          .map((s) => (
            <motion.div
              key={s.key}
              className="relative rounded-lg"
              style={{ background: s.color.fill, boxShadow: `0 0 14px ${s.color.fill}33` }}
              initial={{ width: 0 }}
              animate={{ width: `${s.pct}%` }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              title={`${sourceLabel(s.key)}: ${s.count} of ${total}`}
            />
          ))}
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3">
        {segments.map((s) => (
          <div
            key={s.key}
            className={"rounded-xl border border-border bg-panel/60 px-3 py-2.5 " + (s.count ? "" : "opacity-45")}
          >
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-text-muted">
              <span className="h-2 w-2 rounded-full" style={{ background: s.color.fill }} />
              {sourceLabel(s.key)}
            </div>
            <div className="mt-1 text-2xl font-bold" style={{ color: s.color.fill }}>
              <AnimatedNumber value={s.count} />
            </div>
            <div className="tnum text-[10.5px] text-text-faint">{s.pct.toFixed(0)}% of all actions</div>
          </div>
        ))}
      </div>
    </div>
  )
}
