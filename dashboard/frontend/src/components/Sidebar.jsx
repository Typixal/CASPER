import { WifiOff } from "lucide-react"
import { PAGES } from "../lib/pages"

export default function Sidebar({ page, onNavigate, technical, onToggleTechnical, connected }) {
  return (
    <aside className="flex shrink-0 flex-col border-border bg-navy/90 backdrop-blur-md lg:sticky lg:top-0 lg:h-screen lg:w-64 lg:border-r border-b lg:border-b-0">
      <div className="flex items-baseline gap-2 px-5 pt-5 pb-1">
        <span className="text-xl font-extrabold tracking-[0.14em] text-white">CASPER</span>
      </div>
      <p className="px-5 pb-4 text-[11.5px] leading-snug text-text-faint">
        Gets exam-result portals ready <em>before</em> students arrive.
      </p>

      <nav aria-label="Dashboard pages" className="flex gap-1 overflow-x-auto px-3 pb-3 lg:flex-col lg:overflow-visible">
        {PAGES.map(({ id, label, icon: Icon }) => {
          const active = id === page
          return (
            <a
              key={id}
              href={`#${id}`}
              aria-current={active ? "page" : undefined}
              onClick={(e) => {
                e.preventDefault()
                onNavigate(id)
              }}
              className={
                "flex shrink-0 items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition " +
                (active
                  ? "bg-steel/15 text-white ring-1 ring-steel/40"
                  : "text-text-muted hover:bg-white/5 hover:text-text")
              }
            >
              <Icon size={16} strokeWidth={2.2} className={active ? "text-steel" : ""} aria-hidden="true" />
              {label}
            </a>
          )
        })}
      </nav>

      <div className="mt-auto space-y-3 border-t border-border/70 px-5 py-4">
        <button
          type="button"
          role="switch"
          aria-checked={technical}
          aria-label="Show technical terms"
          onClick={onToggleTechnical}
          className="flex w-full items-center justify-between gap-3 text-left text-[12.5px] text-text-muted"
        >
          <span>Show technical terms</span>
          <span
            className={
              "relative h-5 w-9 shrink-0 rounded-full transition " + (technical ? "bg-steel" : "bg-panel-hover")
            }
          >
            <span
              className={
                "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all " +
                (technical ? "left-[18px]" : "left-0.5")
              }
            />
          </span>
        </button>

        <div className={"flex items-center gap-2 text-xs font-semibold " + (connected ? "text-green" : "text-danger")}>
          {connected ? (
            <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-green" aria-hidden="true" />
          ) : (
            <WifiOff size={12} strokeWidth={2.4} aria-hidden="true" />
          )}
          {connected ? "live updates" : "disconnected"}
        </div>
      </div>
    </aside>
  )
}
