import { sourceColor, sourceLabel, timeOnly } from "../../lib/format"

const HEIGHT = 130
const AXIS_Y = 78
const PAD_X = 28

/**
 * Horizontal timeline of every scale action, oldest -> newest left to right
 * (a deliberate inversion of the newest-first audit table below it, since a
 * timeline reads as a story: "this happened, then this happened"). Markers
 * are colored by `source` and carry an up/down glyph based on whether
 * requested_replicas rose or fell versus the previous action.
 *
 * Pure SVG, no charting library -- viewBox + width:100% so it scales at any
 * breakpoint.
 */
export default function ScaleTimeline({ scaleLog, generatedAt }) {
  const actions = [...(scaleLog?.actions ?? [])].reverse() // newest-first -> oldest-first

  if (!scaleLog?.exists || actions.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center rounded-2xl border border-dashed border-border bg-panel/60 text-text-muted">
        No scale actions recorded yet.
      </div>
    )
  }

  const times = actions.map((a) => new Date(a.timestamp).getTime())
  const minT = Math.min(...times)
  const maxT = Math.max(...times, generatedAt ? new Date(generatedAt).getTime() : 0)
  const span = maxT - minT || 1

  const width = 1000
  const xFor = (t) => PAD_X + ((t - minT) / span) * (width - PAD_X * 2)

  const points = actions.map((action, i) => {
    const prevReq = i > 0 ? actions[i - 1].requested_replicas : null
    const direction = prevReq === null ? "flat" : action.requested_replicas > prevReq ? "up" : action.requested_replicas < prevReq ? "down" : "flat"
    return {
      ...action,
      x: xFor(new Date(action.timestamp).getTime()),
      direction,
      color: sourceColor(action.source),
    }
  })

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${HEIGHT}`} width="100%" height={HEIGHT} preserveAspectRatio="none" className="overflow-visible">
        <line x1={PAD_X} y1={AXIS_Y} x2={width - PAD_X} y2={AXIS_Y} stroke="#D7DEE8" strokeWidth="2" />

        {points.map((p, i) => (
          <g key={i}>
            <title>
              {`${timeOnly(p.timestamp)} — ${sourceLabel(p.source)} — requested ${p.requested_replicas}, healthy ${p.actual_healthy_replicas}\n${(p.replica_names ?? []).join(", ") || "no replicas"}`}
            </title>

            <line x1={p.x} y1={AXIS_Y - 5} x2={p.x} y2={AXIS_Y + 5} stroke={p.color.fill} strokeWidth="2" />
            <circle cx={p.x} cy={AXIS_Y} r="7" fill={p.color.fill} stroke="#FFFFFF" strokeWidth="2" />

            {/* replica count label */}
            <text x={p.x} y={AXIS_Y - 16} textAnchor="middle" fontSize="13" fontWeight="700" fill="#16213E">
              {p.direction === "up" ? "▲" : p.direction === "down" ? "▼" : "•"} {p.requested_replicas}
            </text>

            {/* time label, alternating above/below to reduce crowding */}
            <text
              x={p.x}
              y={i % 2 === 0 ? AXIS_Y + 24 : AXIS_Y + 40}
              textAnchor="middle"
              fontSize="10.5"
              fill="#6B7280"
            >
              {timeOnly(p.timestamp)}
            </text>
          </g>
        ))}
      </svg>

      <div className="mt-2 flex flex-wrap gap-4 text-xs text-text-muted">
        <Legend color="#4A6FA5" label="predictive" />
        <Legend color="#F2994A" label="reactive" />
        <Legend color="#6B7280" label="manual" />
      </div>
    </div>
  )
}

function Legend({ color, label }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  )
}
