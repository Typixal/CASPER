import { AnimatePresence, motion } from "framer-motion"
import { Box, CircleAlert, CircleCheck, Loader, PlugZap, ServerOff } from "lucide-react"

const STATUS = {
  ready: { icon: CircleCheck, color: "text-green", ring: "border-green/40", glow: "shadow-[0_0_22px_-8px_#3FC98D]" },
  starting: { icon: Loader, color: "text-amber", ring: "border-amber/40", glow: "" },
  bad: { icon: CircleAlert, color: "text-danger", ring: "border-danger/40", glow: "" },
}

function classify(replica) {
  if (replica.ready) return "ready"
  if (replica.health === "starting") return "starting"
  return "bad"
}

function EmptyState({ icon: Icon, children }) {
  return (
    <div className="flex h-full min-h-[168px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-center text-text-faint">
      <Icon size={20} />
      <span className="text-sm">{children}</span>
    </div>
  )
}

/**
 * One card per portal replica: health, whether nginx routes to it, probe hits.
 * @param {object} props
 * @param {object} props.docker Snapshot docker state.
 * @param {object} props.probeSummary Snapshot probe_summary.
 * @param {boolean} [props.technical=false] Show container ids and nginx terms.
 */
export default function ReplicaGrid({ docker, probeSummary, technical = false }) {
  if (!docker?.available) {
    return <EmptyState icon={ServerOff}>Docker not reachable — is Docker Desktop running?</EmptyState>
  }

  const replicas = docker.replicas ?? []
  if (!replicas.length) {
    return <EmptyState icon={Box}>No portal containers — the stack is down or drained to 0.</EmptyState>
  }

  const hits = probeSummary?.per_replica ?? {}

  return (
    <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-3">
      <AnimatePresence mode="popLayout">
        {replicas.map((r, i) => {
          const status = STATUS[classify(r)]
          const StatusIcon = status.icon
          // served_by is the container id; match probe hits by prefix.
          const hitKey = Object.keys(hits).find((k) => r.id && (r.id.startsWith(k) || k.startsWith(r.id)))
          const hitCount = hitKey ? hits[hitKey] : 0

          return (
            <motion.article
              key={r.name}
              layout
              initial={{ opacity: 0, scale: 0.9, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9 }}
              transition={{ duration: 0.3, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
              className={`rounded-xl border bg-panel/70 p-3 ${status.ring} ${status.glow}`}
            >
              <div className="flex items-center gap-1.5">
                <StatusIcon
                  size={14}
                  strokeWidth={2.4}
                  className={`${status.color} ${classify(r) === "starting" ? "animate-spin" : ""}`}
                />
                <span className="truncate text-sm font-semibold text-text">
                  {technical ? `portal-${r.short_name}` : `server ${r.short_name}`}
                </span>
              </div>

              <div className="mt-1.5 text-[11px] text-text-faint">
                {r.state} &middot; {r.health || "no healthcheck"}
              </div>

              <div
                className={
                  "mt-2 flex items-center gap-1 text-[11px] font-medium " +
                  (r.routed ? "text-green" : "text-amber")
                }
              >
                <PlugZap size={12} strokeWidth={2.4} />
                {technical
                  ? r.routed
                    ? "in nginx upstream"
                    : "not in nginx"
                  : r.routed
                    ? "receiving visitors"
                    : "not receiving visitors yet"}
              </div>

              <div className="mt-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 border-t border-border/60 pt-2 text-[10.5px] text-text-faint">
                {technical && <span className="truncate font-mono">{r.id || "?"}</span>}
                <span className="tnum">
                  {hitCount} {technical ? `hit${hitCount === 1 ? "" : "s"}` : `test visit${hitCount === 1 ? "" : "s"}`}
                </span>
              </div>
            </motion.article>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
