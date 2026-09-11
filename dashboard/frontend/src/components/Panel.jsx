import { motion } from "framer-motion"

/**
 * Shared panel shell: subtle raised surface, icon + title header, optional
 * tag and right-aligned slot. Fades/slides in once on mount so the page
 * assembles itself rather than snapping into place.
 */
export default function Panel({ icon: Icon, title, tag, right, className = "", bodyClassName = "", children, delay = 0 }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: [0.22, 1, 0.36, 1] }}
      className={
        "flex flex-col rounded-2xl border border-border bg-panel-raised/80 shadow-[0_2px_24px_-12px_rgba(0,0,0,0.9)] backdrop-blur-sm " +
        className
      }
    >
      <header className="flex flex-wrap items-center gap-2.5 border-b border-border/70 px-5 py-3.5">
        {Icon && <Icon size={15} className="shrink-0 text-steel" strokeWidth={2.2} />}
        <h2 className="text-[12.5px] font-semibold uppercase tracking-[0.13em] text-text-muted">{title}</h2>
        {tag && (
          <span className="rounded-full border border-border bg-panel px-2.5 py-0.5 text-[10.5px] font-medium text-text-faint">
            {tag}
          </span>
        )}
        {right && <div className="ml-auto">{right}</div>}
      </header>
      <div className={`flex min-h-0 flex-1 flex-col px-5 py-4 ${bodyClassName}`}>{children}</div>
    </motion.section>
  )
}
