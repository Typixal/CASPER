import { Globe, Radio, WifiOff } from "lucide-react"
import { motion } from "framer-motion"

export default function Masthead({ entrypoint, connected, probeEnabled, onToggleProbe, probePending }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border/80 bg-navy/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
        <motion.div
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-baseline gap-2.5"
        >
          <span className="text-xl font-extrabold tracking-[0.14em] text-white">CASPER</span>
          <span className="hidden text-[13px] font-medium text-text-muted sm:inline">
            civic-event-aware predictive scaling
          </span>
        </motion.div>

        <span className="flex items-center gap-1.5 rounded-full border border-border bg-panel/70 px-3 py-1 font-mono text-[11.5px] text-text-muted">
          <Globe size={12} strokeWidth={2.2} className="text-text-faint" />
          {entrypoint?.replace(/^https?:\/\//, "") ?? "localhost:8080"}
        </span>

        <div className="flex-1" />

        <button
          type="button"
          onClick={onToggleProbe}
          disabled={probePending}
          title="The dashboard's own latency probe — turn it off before a Module D k6 run"
          className={
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 " +
            (probeEnabled
              ? "border-steel/40 bg-steel/10 text-steel hover:bg-steel/20"
              : "border-border bg-panel/60 text-text-faint hover:border-border-bright")
          }
        >
          <Radio size={13} strokeWidth={2.4} className={probeEnabled ? "pulse-dot" : ""} />
          probe {probeEnabled ? "on" : "off"}
        </button>

        <span
          className={
            "flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold " +
            (connected ? "border-green/40 bg-green/10 text-green" : "border-danger/40 bg-danger/10 text-danger")
          }
        >
          {connected ? (
            <>
              <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-green" />
              live
            </>
          ) : (
            <>
              <WifiOff size={12} strokeWidth={2.4} />
              disconnected
            </>
          )}
        </span>
      </div>
    </header>
  )
}
