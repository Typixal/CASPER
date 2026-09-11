const WIDTH = 900
const HEIGHT = 220
const PAD_L = 42
const PAD_R = 12
const PAD_T = 12
const PAD_B = 24

/**
 * Line + soft area chart of the dashboard's own latency probe history
 * (probe_summary.history, a ring buffer of up to 90 samples). Gridlines and
 * ms labels replace the old bare hand-drawn line. Still pure inline SVG, no
 * charting library, scaled via viewBox so it's responsive.
 */
export default function LatencyChart({ probeSummary }) {
  const history = probeSummary?.history ?? []

  if (!history.length) {
    return (
      <div className="flex h-[220px] items-center justify-center rounded-2xl border border-dashed border-border bg-panel/60 text-text-muted">
        Probe disabled or no samples yet.
      </div>
    )
  }

  const okValues = history.filter((h) => h.ok && h.latency_ms != null).map((h) => h.latency_ms)
  const maxV = Math.max(50, ...okValues)
  const plotW = WIDTH - PAD_L - PAD_R
  const plotH = HEIGHT - PAD_T - PAD_B
  const stepX = history.length > 1 ? plotW / (history.length - 1) : 0

  const xAt = (i) => PAD_L + i * stepX
  const yAt = (v) => PAD_T + plotH - (v / maxV) * plotH

  let linePath = ""
  let areaPath = ""
  let started = false
  history.forEach((h, i) => {
    if (h.ok && h.latency_ms != null) {
      const x = xAt(i)
      const y = yAt(h.latency_ms)
      linePath += (started ? " L" : " M") + `${x.toFixed(1)},${y.toFixed(1)}`
      if (!started) {
        areaPath += `M${x.toFixed(1)},${(PAD_T + plotH).toFixed(1)} L${x.toFixed(1)},${y.toFixed(1)}`
      } else {
        areaPath += ` L${x.toFixed(1)},${y.toFixed(1)}`
      }
      started = true
    } else {
      started = false
    }
  })
  if (areaPath) {
    const lastOkIndex = history.map((h) => h.ok && h.latency_ms != null).lastIndexOf(true)
    areaPath += ` L${xAt(lastOkIndex).toFixed(1)},${(PAD_T + plotH).toFixed(1)} Z`
  }

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    y: PAD_T + plotH * (1 - f),
    label: Math.round(maxV * f),
  }))

  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" height={HEIGHT} preserveAspectRatio="none">
        {gridLines.map((g, i) => (
          <g key={i}>
            <line x1={PAD_L} y1={g.y} x2={WIDTH - PAD_R} y2={g.y} stroke="#D7DEE8" strokeWidth="1" />
            <text x={PAD_L - 8} y={g.y + 4} textAnchor="end" fontSize="11" fill="#6B7280">
              {g.label}
            </text>
          </g>
        ))}

        {/* failed-probe markers */}
        {history.map((h, i) =>
          h.ok ? null : (
            <rect
              key={`fail-${i}`}
              x={xAt(i) - 2}
              y={PAD_T}
              width="4"
              height={plotH}
              fill="#D64545"
              opacity="0.35"
            />
          ),
        )}

        {areaPath && <path d={areaPath} fill="#4A6FA5" opacity="0.12" />}
        {linePath && <path d={linePath} fill="none" stroke="#4A6FA5" strokeWidth="2.5" />}

        {history.map((h, i) =>
          h.ok && h.latency_ms != null ? (
            <circle key={`pt-${i}`} cx={xAt(i)} cy={yAt(h.latency_ms)} r="3" fill="#4A6FA5">
              <title>{`${h.latency_ms} ms — ${h.served_by ?? "unknown replica"}`}</title>
            </circle>
          ) : null,
        )}
      </svg>

      <div className="mt-2 flex flex-wrap gap-5 text-xs text-text-muted">
        <span>
          avg <b className="text-text">{probeSummary.avg_ms ?? "—"} ms</b>
        </span>
        <span>
          max <b className="text-text">{probeSummary.max_ms ?? "—"} ms</b>
        </span>
        <span>
          failed{" "}
          <b className={probeSummary.error_count ? "text-danger" : "text-text"}>
            {probeSummary.error_count ?? 0}
          </b>{" "}
          / {probeSummary.samples ?? 0}
        </span>
      </div>
    </div>
  )
}
