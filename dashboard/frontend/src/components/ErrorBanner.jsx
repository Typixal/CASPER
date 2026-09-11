import { AlertTriangle, Loader } from "lucide-react"
import { motion } from "framer-motion"

/**
 * One global banner for conditions that make the whole page unreliable:
 * startup, a fatal collector exception, or Docker being unreachable.
 * Narrower per-subsystem errors render inside their own panel instead, so
 * one broken source doesn't hide the panels that are fine.
 */
export default function ErrorBanner({ state }) {
  if (state.starting) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center gap-2 rounded-xl border border-border bg-panel/70 px-4 py-2.5 text-sm text-text-muted"
      >
        <Loader size={15} className="animate-spin" />
        Waiting for the first snapshot…
      </motion.div>
    )
  }

  const message = state.fatal_error
    ? `Dashboard error: ${state.fatal_error}`
    : state.docker && !state.docker.available
      ? `Docker unreachable: ${state.docker.error ?? "unknown error"} — is Docker Desktop running?`
      : null

  if (!message) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-2.5 rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger"
    >
      <AlertTriangle size={16} className="shrink-0" />
      {message}
    </motion.div>
  )
}
