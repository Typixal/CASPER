/**
 * A single global banner for conditions that make the whole page unreliable
 * (startup, a fatal collector exception, or Docker being unreachable --
 * which affects nearly every panel). Narrower per-subsystem errors
 * (nginx.error, scale_log.error, prediction.error, probe.error) are shown
 * inline inside their own panel instead, so one broken data source doesn't
 * hide the ones that are fine.
 */
export default function ErrorBanner({ state }) {
  if (state.starting) {
    return (
      <div className="mx-4 mt-4 rounded-lg border border-border bg-panel px-4 py-3 text-sm text-text-muted sm:mx-6">
        Waiting for the first snapshot…
      </div>
    )
  }

  const message = state.fatal_error
    ? `Dashboard error: ${state.fatal_error}`
    : state.docker && !state.docker.available
      ? `Docker unreachable: ${state.docker.error ?? "unknown error"} — is Docker Desktop running?`
      : null

  if (!message) return null

  return (
    <div className="mx-4 mt-4 rounded-lg border border-danger/40 bg-danger-bg px-4 py-3 text-sm text-danger sm:mx-6">
      {message}
    </div>
  )
}
