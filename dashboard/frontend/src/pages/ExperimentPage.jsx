import { FlaskConical, Scale, Trophy } from "lucide-react"
import PageHeader from "../components/PageHeader"
import { describeComparison } from "../lib/comparison"
import { sourceColor } from "../lib/format"
import { term } from "../lib/terms"

const ROWS = [
  { key: "p95_ms", term: "p95", fmt: (v, t) => (t ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(2)} s`) },
  { key: "error_rate", term: "error_rate", fmt: (v) => `${(v * 100).toFixed(2)}%` },
  { key: "success_pct", term: "success_pct", fmt: (v) => `${v.toFixed(2)}%` },
  { key: "replica_seconds", term: "replica_seconds", fmt: (v) => Math.round(v).toLocaleString("en-US") },
]
const STRATEGIES = ["reactive", "predictive"]

function ResultsTable({ comparison, technical }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[520px] border-collapse text-[14px]">
        <thead>
          <tr className="bg-panel text-left text-[11px] uppercase tracking-wider text-text-faint">
            <th className="px-4 py-2.5 font-semibold">measure</th>
            {STRATEGIES.map((s) => (
              <th key={s} className="px-4 py-2.5 font-semibold" style={{ color: sourceColor(s).fill }}>
                {term(s, technical)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row) => (
            <tr key={row.key} className="border-t border-border/60">
              <td className="px-4 py-3 text-text-muted">{term(row.term, technical)}</td>
              {STRATEGIES.map((s) => {
                const won = comparison.verdict?.[row.key] === s
                return (
                  <td key={s} className={`tnum px-4 py-3 ${won ? "font-bold text-text" : "text-text-muted"}`}>
                    <span className="inline-flex items-center gap-1.5">
                      {row.fmt(comparison[s][row.key], technical)}
                      {won && <Trophy size={13} className="text-green" aria-label="better" />}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Chart({ src, alt, caption }) {
  return (
    <figure className="overflow-hidden rounded-2xl border border-border bg-white">
      <img src={src} alt={alt} className="w-full" />
      <figcaption className="border-t border-border bg-panel-raised px-4 py-2.5 text-[12.5px] text-text-muted">
        {caption}
      </figcaption>
    </figure>
  )
}

export default function ExperimentPage({ comparison, technical = false }) {
  const story = describeComparison(comparison, technical)

  return (
    <>
      <PageHeader title="Experiment: does planning ahead work?">
        The same burst of exam-day visitors was sent to the portal twice — once with a {term("reactive", technical)}{" "}
        that only adds {term("replicas", technical)} when pages get slow, and once with CASPER, which adds them before
        the rush from the calendar.
      </PageHeader>

      {!story ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-12 text-center text-text-faint">
          <FlaskConical size={22} aria-hidden="true" />
          <span>No experiment has been run yet.</span>
          <code className="rounded bg-panel px-2.5 py-1 font-mono text-[12.5px] text-text-muted">.\run-demo.ps1 -Compare</code>
          <span className="text-[12.5px]">About 9 minutes; the result appears here when it finishes.</span>
        </div>
      ) : (
        <div className="space-y-6">
          <section className="rounded-3xl border border-steel/40 bg-steel/10 p-6 sm:p-8">
            <h2 className="text-3xl font-bold leading-tight text-text sm:text-4xl">{story.headline}</h2>
            <ul className="mt-4 space-y-2 text-[15.5px] leading-relaxed text-text-muted">
              {story.points.map((point) => (
                <li key={point} className="flex gap-2">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-steel" aria-hidden="true" />
                  {point}
                </li>
              ))}
            </ul>
          </section>

          <ResultsTable comparison={comparison} technical={technical} />

          <div className="flex gap-3 rounded-2xl border border-border bg-panel-raised/70 p-5 text-[14px] leading-relaxed text-text-muted">
            <Scale size={18} className="mt-0.5 shrink-0 text-steel" aria-hidden="true" />
            <p>
              <b className="text-text">Why it's a fair test:</b> both runs got exactly the same visitors at exactly the
              same moments, started from the same single {term("replica", technical)}, and changed {term("replicas", technical)}{" "}
              through the same control switch. The only difference is <i>who decides when</i>. The autoscaler isn't
              handicapped — it uses the standard safeguards real autoscalers use. It simply can't react to visitors who
              haven't arrived yet.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
            <Chart
              src="/api/results/latency_over_time.png"
              alt="Page load times and servers over time, for both strategies"
              caption="Top: how slow the slowest page loads were, second by second. Bottom: how many servers were running. CASPER's servers arrive before the dashed line (the rush); the autoscaler's arrive after it."
            />
            <Chart
              src="/api/results/summary_bars.png"
              alt="The three headline numbers side by side"
              caption="The three headline numbers, side by side. These charts are also saved in module-d-evaluation/results/ for the report."
            />
          </div>
        </div>
      )}
    </>
  )
}
