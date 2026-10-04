import { FlaskConical, Trophy } from "lucide-react"
import { sourceColor } from "../lib/format"

const ROWS = [
  { key: "p95_ms", label: "p95 response time", fmt: (v) => `${Math.round(v)} ms` },
  { key: "error_rate", label: "error rate", fmt: (v) => `${(v * 100).toFixed(2)}%` },
  { key: "success_pct", label: "successful requests", fmt: (v) => `${v.toFixed(2)}%` },
  { key: "replica_seconds", label: "replica-seconds (cost)", fmt: (v) => Math.round(v).toLocaleString() },
]

const COLUMNS = [
  { key: "reactive", label: "Reactive baseline" },
  { key: "predictive", label: "Predictive (CASPER)" },
]

/**
 * The experiment's answer: same traffic, same infrastructure, same scale
 * controller -- only the brain differs. Shows a placeholder until Module D
 * has produced results/comparison.json.
 */
export default function ComparisonPanel({ comparison }) {
  if (!comparison) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 py-8 text-center text-text-faint">
        <FlaskConical size={20} />
        <span className="text-sm">No comparison run yet.</span>
        <code className="rounded bg-panel px-2 py-1 font-mono text-[11.5px] text-text-muted">
          .\run-demo.ps1 -Compare
        </code>
      </div>
    )
  }

  const reduction = comparison.p95_reduction_pct

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-4xl font-extrabold text-steel tnum">
          {reduction > 0 ? `${reduction.toFixed(1)}%` : "—"}
        </span>
        <span className="text-sm text-text-muted">
          {reduction > 0 ? "lower p95 response time with CASPER" : "no p95 improvement in this run"}
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[520px] border-collapse text-[13px]">
          <thead>
            <tr className="bg-panel text-left text-[10.5px] uppercase tracking-wider text-text-faint">
              <th className="px-3 py-2 font-semibold">metric</th>
              {COLUMNS.map((c) => (
                <th key={c.key} className="px-3 py-2 font-semibold" style={{ color: sourceColor(c.key).fill }}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => {
              const winner = comparison.verdict?.[row.key]
              return (
                <tr key={row.key} className="border-t border-border/60">
                  <td className="px-3 py-2.5 text-text-muted">{row.label}</td>
                  {COLUMNS.map((c) => {
                    const won = winner === c.key
                    return (
                      <td key={c.key} className={`tnum px-3 py-2.5 ${won ? "font-bold text-text" : "text-text-muted"}`}>
                        <span className="inline-flex items-center gap-1.5">
                          {row.fmt(comparison[c.key][row.key])}
                          {won && <Trophy size={12} className="text-green" strokeWidth={2.5} />}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-text-faint">
        Replica-seconds is the honest cost of predicting: CASPER provisions before the traffic arrives,
        so some of that capacity sits idle first. Charts for the report are in{" "}
        <code className="font-mono">module-d-evaluation/results/</code>.
      </p>
    </div>
  )
}
