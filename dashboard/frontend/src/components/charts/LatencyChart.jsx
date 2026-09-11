import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { Radio } from "lucide-react"

const STEEL = "#6E9BE0"
const DANGER = "#FF5F66"

function ProbeTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-border-bright bg-panel px-3 py-2 text-xs shadow-xl">
      <div className="tnum font-semibold text-text">
        {point.failed ? "request failed" : `${point.latency} ms`}
      </div>
      <div className="mt-0.5 font-mono text-[11px] text-text-faint">{point.clock}</div>
      {point.served_by && (
        <div className="mt-1 font-mono text-[11px] text-steel">served by {point.served_by}</div>
      )}
    </div>
  )
}

/**
 * Probe latency over time. The dashboard's own request, once per refresh --
 * labelled as such so it is never confused with Module D's k6 numbers.
 * Failed probes (a drained stack returning 502) are drawn as red reference
 * lines rather than silently breaking the series.
 */
export default function LatencyChart({ probeSummary, probeEnabled }) {
  const history = probeSummary?.history ?? []

  if (!history.length) {
    return (
      <div className="flex min-h-[230px] flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-text-faint">
        <Radio size={20} />
        <span className="text-sm">{probeEnabled ? "waiting for samples…" : "probe is switched off"}</span>
      </div>
    )
  }

  const data = history.map((h, i) => ({
    i,
    latency: h.ok ? h.latency_ms : null,
    failed: !h.ok,
    served_by: h.served_by,
    clock: h.at ? new Date(h.at).toLocaleTimeString() : "",
  }))

  const failures = data.filter((d) => d.failed)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-[230px] w-full flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <defs>
              <linearGradient id="latencyFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={STEEL} stopOpacity={0.45} />
                <stop offset="100%" stopColor={STEEL} stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid stroke="#233150" strokeDasharray="3 4" vertical={false} />
            <XAxis dataKey="i" hide />
            <YAxis
              tick={{ fill: "#5D6B8F", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={44}
              tickFormatter={(v) => `${v}`}
              label={{
                value: "ms",
                position: "insideTopLeft",
                offset: -2,
                style: { fill: "#5D6B8F", fontSize: 10 },
              }}
            />
            <Tooltip content={<ProbeTooltip />} cursor={{ stroke: STEEL, strokeDasharray: "3 3" }} />

            {failures.map((f) => (
              <ReferenceLine key={f.i} x={f.i} stroke={DANGER} strokeOpacity={0.45} strokeWidth={3} />
            ))}

            <Area
              type="monotone"
              dataKey="latency"
              stroke={STEEL}
              strokeWidth={2.4}
              fill="url(#latencyFill)"
              connectNulls={false}
              isAnimationActive
              animationDuration={450}
              dot={false}
              activeDot={{ r: 4, fill: STEEL, stroke: "#0B1020", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t border-border/60 pt-3 text-xs text-text-faint">
        <span>
          avg <b className="tnum text-text">{probeSummary.avg_ms ?? "—"}</b> ms
        </span>
        <span>
          max <b className="tnum text-text">{probeSummary.max_ms ?? "—"}</b> ms
        </span>
        <span>
          failed{" "}
          <b className={`tnum ${probeSummary.error_count ? "text-danger" : "text-text"}`}>
            {probeSummary.error_count ?? 0}
          </b>{" "}
          / {probeSummary.samples ?? 0}
        </span>
      </div>
    </div>
  )
}
