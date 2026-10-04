import { motion } from "framer-motion"
import { CircleDashed, CircleCheckBig } from "lucide-react"

/**
 * Status card for Module A, B or D; dimmed until its artifacts exist.
 * @param {object} props
 * @param {string} props.title
 * @param {object} props.module Entry from snapshot modules.
 * @param {number} [props.delay=0] Entrance animation delay, seconds.
 */
export default function ModulePanel({ title, module, delay = 0, children }) {
  const built = module?.built

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className={
        "rounded-2xl border p-4 " +
        (built
          ? "border-green/35 bg-panel-raised/70 shadow-[0_0_26px_-14px_#3FC98D]"
          : "border-dashed border-border bg-panel/40")
      }
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className={`text-[13px] font-semibold ${built ? "text-text" : "text-text-muted"}`}>{title}</h3>
        {built ? (
          <span className="flex items-center gap-1 rounded-full border border-green/40 bg-green/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-green">
            <CircleCheckBig size={10} strokeWidth={2.8} />
            live
          </span>
        ) : (
          <span className="flex items-center gap-1 rounded-full border border-dashed border-border px-2 py-0.5 text-[10px] text-text-faint">
            <CircleDashed size={10} strokeWidth={2.4} />
            not built
          </span>
        )}
      </div>

      <div className={`mt-2.5 space-y-1 text-[11.5px] leading-relaxed ${built ? "text-text-muted" : "text-text-faint"}`}>
        {children}
      </div>
    </motion.div>
  )
}
