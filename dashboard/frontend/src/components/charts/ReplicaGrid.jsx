const STATUS_STYLE = {
  ready: { border: "border-l-green", dot: "bg-green" },
  starting: { border: "border-l-amber", dot: "bg-amber" },
  bad: { border: "border-l-danger", dot: "bg-danger" },
}

function classify(replica) {
  if (replica.ready) return "ready"
  if (replica.health === "starting") return "starting"
  return "bad"
}

export default function ReplicaGrid({ docker, probeSummary }) {
  if (!docker?.available) {
    return (
      <div className="flex h-full min-h-[140px] items-center justify-center rounded-2xl border border-dashed border-border bg-panel/60 text-center text-text-muted">
        Docker not reachable — is Docker Desktop running?
      </div>
    )
  }

  const replicas = docker.replicas ?? []
  if (!replicas.length) {
    return (
      <div className="flex h-full min-h-[140px] items-center justify-center rounded-2xl border border-dashed border-border bg-panel/60 text-center text-text-muted">
        No portal containers. Stack is down or drained to 0.
      </div>
    )
  }

  const hits = probeSummary?.per_replica ?? {}

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {replicas.map((r) => {
        const status = STATUS_STYLE[classify(r)]
        const hitKey = Object.keys(hits).find((k) => r.id && (r.id.startsWith(k) || k.startsWith(r.id)))
        const hitCount = hitKey ? hits[hitKey] : 0

        return (
          <div
            key={r.name}
            className={`rounded-xl border border-l-4 border-border bg-panel-raised p-3 shadow-sm ${status.border}`}
          >
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${status.dot}`} />
              <span className="truncate text-sm font-semibold text-navy">{r.short_name}</span>
            </div>
            <div className="mt-1 text-xs text-text-muted">
              {r.state} &middot; {r.health || "—"}
            </div>
            <div className={`mt-1.5 text-xs font-medium ${r.routed ? "text-green" : "text-amber"}`}>
              {r.routed ? "● in nginx" : "● not in nginx"}
            </div>
            <div className="mt-1 flex items-center justify-between text-[11px] text-text-faint">
              <span className="font-mono">{r.id || "?"}</span>
              <span>{hitCount} hit{hitCount === 1 ? "" : "s"}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
