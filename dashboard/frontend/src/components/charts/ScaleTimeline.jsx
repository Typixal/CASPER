import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { History } from "lucide-react"
import { sourceColor, sourceLabel, timeOnly } from "../../lib/format"

/**
 * Capacity over time — a staircase of every scale action, oldest to newest
 * (a deliberate inversion of the newest-first audit table below: a timeline
 * reads as a story). Step interpolation is the honest shape here: replica
 * count holds flat between actions and jumps at one, it does not glide.
 *
 * Each point is colored by which brain asked for it, so "CASPER scaled up
 * before the traffic" is visible as a blue step that lands early.
 */
function SourceDot({ cx, cy, payload }) {
  if (cx == null || cy == null) return null
  const color = sourceColor(payload.source).fill
  return (
    <g>
      <circle cx={cx} cy={cy} r={7} fill={color} fillOpacity={0.22} />
      <circle cx={cx} cy={cy} r={4} fill={color} stroke="#0B1020" strokeWidth={1.5} />
    </g>
  )
}

function TimelineTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const color = sourceColor(p.source)
  return (
    <div className="max-w-xs rounded-lg border border-border-bright bg-panel px-3 py-2 text-xs shadow-xl">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color.fill }} />
        <span className="font-semibold" style={{ color: color.fill }}>
          {sourceLabel(p.source)}
        </span>
        <span className="font-mono text-[11px] text-text-faint">{p.clock}</span>
      </div>
      <div className="mt-1.5 text-text">
        requested <b className="tnum">{p.requested}</b> &middot; healthy{" "}
        <b className={`tnum ${p.healthy !== p.requested ? "text-amber" : ""}`}>{p.healthy}</b>
      </div>
      {p.replicas && <div className="mt-1 font-mono text-[10.5px] text-text-faint">{p.replicas}</div>}
    </div>
  )
}

export default function ScaleTimeline({ scaleLog }) {
  const actions = [...(scaleLog?.actions ?? [])].reverse() // collector sends newest-first

  if (!scaleLog?.exists || actions.length === 0) {
    return (
      <div className="flex min-h-[220px] flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-text-faint">
        <History size={20} />
        <span className="text-sm">No scale actions recorded yet.</span>
      </div>
    )
  }

  const data = actions.map((a, i) => ({
    i,
    requested: a.requested_replicas,
    healthy: a.actual_healthy_replicas,
    source: a.source,
    clock: timeOnly(a.timestamp),
    replicas: (a.replica_names ?? []).join(", "),
  }))

  const maxReplicas = Math.max(1, ...data.map((d) => d.requested))

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-[220px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: -20 }}>
            <CartesianGrid stroke="#233150" strokeDasharray="3 4" vertical={false} />
            <XAxis
              dataKey="clock"
              tick={{ fill: "#5D6B8F", fontSize: 10.5 }}
              axisLine={{ stroke: "#233150" }}
              tickLine={false}
              minTickGap={28}
            />
            <YAxis
              tick={{ fill: "#5D6B8F", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={46}
              allowDecimals={false}
              domain={[0, maxReplicas + 1]}
              label={{
                value: "replicas",
                angle: -90,
                position: "insideLeft",
                offset: 26,
                style: { fill: "#5D6B8F", fontSize: 10.5 },
              }}
            />
            <Tooltip content={<TimelineTooltip />} cursor={{ stroke: "#33456E", strokeDasharray: "3 3" }} />
            <Line
              type="stepAfter"
              dataKey="requested"
              stroke="#33456E"
              strokeWidth={2}
              dot={<SourceDot />}
              activeDot={false}
              isAnimationActive
              animationDuration={500}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap gap-4 border-t border-border/60 pt-3 text-xs text-text-faint">
        {["predictive", "reactive", "manual"].map((key) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: sourceColor(key).fill }} />
            {key}
          </span>
        ))}
      </div>
    </div>
  )
}
