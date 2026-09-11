import { sourceColor, sourceLabel, timeOnly } from "../lib/format"

/**
 * The exact newest-first table the old dashboard showed as its primary
 * view. Nothing is dropped in the redesign -- it's demoted to a collapsible
 * detail view under the new timeline chart, for whoever wants exact values.
 */
export default function AuditTable({ actions }) {
  if (!actions?.length) return null

  return (
    <details className="mt-4 group">
      <summary className="cursor-pointer select-none text-sm font-medium text-steel hover:text-navy">
        Show exact log ({actions.length} action{actions.length === 1 ? "" : "s"}, newest first)
      </summary>

      <div className="mt-3 overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[560px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-panel text-left text-[11px] uppercase tracking-wider text-text-muted">
              <th className="px-3 py-2 font-semibold">Time</th>
              <th className="px-3 py-2 font-semibold">Source</th>
              <th className="px-3 py-2 font-semibold">Requested</th>
              <th className="px-3 py-2 font-semibold">Healthy</th>
              <th className="px-3 py-2 font-semibold">Replicas</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((a, i) => {
              const color = sourceColor(a.source)
              const shortfall = a.actual_healthy_replicas !== a.requested_replicas
              return (
                <tr key={i} className="border-b border-border/60 last:border-b-0">
                  <td className="px-3 py-2 font-mono text-xs text-text-muted">{timeOnly(a.timestamp)}</td>
                  <td className="px-3 py-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${color.text} bg-current/10`}>
                      {sourceLabel(a.source)}
                    </span>
                  </td>
                  <td className="px-3 py-2">{a.requested_replicas}</td>
                  <td className={`px-3 py-2 ${shortfall ? "font-semibold text-amber" : ""}`}>
                    {a.actual_healthy_replicas}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-text-muted">
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
