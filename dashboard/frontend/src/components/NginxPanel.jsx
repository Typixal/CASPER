import { AlertTriangle, ArrowRightLeft, FileCode2 } from "lucide-react"
import { motion } from "framer-motion"
import { timeOnly } from "../lib/format"

export default function NginxPanel({ nginx }) {
  if (!nginx?.exists) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-text-faint">
        <FileCode2 size={16} />
        nginx.conf not generated yet — run the controller once.
      </div>
    )
  }

  if (nginx.error) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-danger">
        <AlertTriangle size={16} />
        {nginx.error}
      </div>
    )
  }

  return (
    <div>
      {nginx.drained && (
        <div className="mb-3 flex items-start gap-2 rounded-xl border border-amber/40 bg-amber/10 px-3 py-2.5 text-[11.5px] text-amber">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>
            Drained to zero — upstream holds the placeholder{" "}
            <code className="font-mono">server 127.0.0.1:1 down;</code>, so nginx returns 502.
          </span>
        </div>
      )}

      {nginx.servers?.length ? (
        <ul className="space-y-1.5">
          {nginx.servers.map((s, i) => (
            <motion.li
              key={s}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.25, delay: i * 0.04 }}
              className="flex items-center justify-between rounded-lg border border-border/70 bg-panel/60 px-3 py-2"
            >
              <span className="flex items-center gap-2 font-mono text-[12px] text-text">
                <ArrowRightLeft size={12} className="text-steel" strokeWidth={2.4} />
                {s}
              </span>
              <span className="text-[10.5px] font-semibold uppercase tracking-wider text-green">routing</span>
            </motion.li>
          ))}
        </ul>
      ) : (
        <div className="py-4 text-center text-sm text-text-faint">no upstream servers</div>
      )}

      <div className="mt-3 border-t border-border/60 pt-2.5 text-[11px] text-text-faint">
        config last written {timeOnly(nginx.modified)}
      </div>
    </div>
  )
}
