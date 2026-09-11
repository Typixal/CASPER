import { ChevronRight } from "lucide-react"
import { sourceColor, sourceLabel, timeOnly } from "../lib/format"

/**
 * The exact newest-first log. The timeline chart above is the primary view;
 * this is kept as a collapsible detail for anyone who wants precise values
 * (which replicas, exact requested-vs-healthy counts).
 */
export default function AuditTable({ actions }) {
  if (!actions?.length) return null

  return (
    <details className="group mt-4">
      <summary className="flex cursor-pointer select-none items-center gap-1 text-[12px] font-medium text-text-muted transition hover:text-steel">
        <ChevronRight size={14} className="transition-transform group-open:rotate-90" />
        exact log — {actions.length} action{actions.length === 1 ? "" : "s"}, newest first
      </summary>

      <div className="mt-3 overflow-x-auto rounded-xl border border-border">
        <table className="w-full min-w-[580px] border-collapse text-[12.5px]">
          <thead>
            <tr className="bg-panel text-left text-[10.5px] uppercase tracking-wider text-text-faint">
              <th className="px-3 py-2 font-semibold">time</th>
              <th className="px-3 py-2 font-semibold">source</th>
              <th className="px-3 py-2 font-semibold">requested</th>
              <th className="px-3 py-2 font-semibold">healthy</th>
              <th className="px-3 py-2 font-semibold">replicas</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((a, i) => {
              const color = sourceColor(a.source)
              const shortfall = a.actual_healthy_replicas !== a.requested_replicas
              return (
                <tr key={i} className="border-t border-border/60 transition hover:bg-panel/60">
                  <td className="px-3 py-2 font-mono text-[11.5px] text-text-faint">{timeOnly(a.timestamp)}</td>
                  <td className="px-3 py-2">
                    <span
                      className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
                      style={{ color: color.fill, background: `${color.fill}1f` }}
                    >
                      {sourceLabel(a.source)}
                    </span>
                  </td>
                  <td className="tnum px-3 py-2 text-text">{a.requested_replicas}</td>
                  <td className={`tnum px-3 py-2 ${shortfall ? "font-semibold text-amber" : "text-text"}`}>
                    {a.actual_healthy_replicas}
                  </td>
                  <td className="px-3 py-2 font-mono text-[11px] text-text-faint">
                    {(a.replica_names ?? []).join(", ") || "—"}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}
