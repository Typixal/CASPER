export default function Masthead({ entrypoint, connected, probeEnabled, onToggleProbe, probePending }) {
  return (
    <header className="sticky top-0 z-20 flex flex-wrap items-center gap-3 bg-navy px-4 py-3 text-white sm:px-6">
      <div className="flex items-baseline gap-2">
        <h1 className="text-lg font-bold tracking-wide sm:text-xl">CASPER</h1>
        <span className="hidden text-sm font-normal text-white/60 sm:inline">
          live demo dashboard
        </span>
      </div>

      <span className="rounded-full border border-white/20 px-3 py-1 font-mono text-xs text-white/70">
        {entrypoint ?? "localhost:8080"}
      </span>

      <div className="flex-1" />

      <button
        type="button"
        onClick={onToggleProbe}
        disabled={probePending}
        className="rounded-lg border border-white/20 bg-white/5 px-3 py-1.5 text-xs font-medium text-white transition hover:border-steel hover:bg-white/10 disabled:opacity-50"
      >
        probe {probeEnabled ? "on" : "off"} &middot; toggle
      </button>

      <span
        className={
          "flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold " +
          (connected
            ? "border-green/50 text-green"
            : "border-danger/50 text-danger")
        }
      >
        <span
          className={
            "h-2 w-2 rounded-full " + (connected ? "bg-green" : "bg-danger")
          }
        />
        {connected ? "live" : "disconnected"}
      </span>
    </header>
  )
}
