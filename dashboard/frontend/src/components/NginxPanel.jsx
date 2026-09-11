import { timeOnly } from "../lib/format"

export default function NginxPanel({ nginx }) {
  if (!nginx?.exists) {
    return <div className="text-sm text-text-muted">nginx.conf not generated yet — run the controller once.</div>
  }

  if (nginx.error) {
    return <div className="text-sm text-danger">{nginx.error}</div>
  }

  return (
    <div>
      {nginx.drained && (
        <div className="mb-3 rounded-lg border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-amber">
          Drained to zero — placeholder <code className="font-mono">server 127.0.0.1:1 down;</code> in upstream,
          nginx returns 502.
        </div>
      )}

      {nginx.servers?.length ? (
        <ul className="space-y-1.5">
          {nginx.servers.map((s) => (
            <li key={s} className="flex items-center justify-between rounded-md bg-panel px-3 py-1.5 text-sm">
              <span className="font-mono text-text">{s}</span>
              <span className="text-xs font-medium text-green">routing</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-text-muted">no upstream servers</div>
      )}

      <div className="mt-3 text-xs text-text-muted">config last written {timeOnly(nginx.modified)}</div>
    </div>
  )
}
