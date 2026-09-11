export default function Panel({ title, tag, className = "", children }) {
  return (
    <div className={`rounded-2xl border border-border bg-panel-raised p-5 shadow-sm ${className}`}>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <h2 className="text-xs font-bold uppercase tracking-wider text-text-muted">{title}</h2>
        {tag && (
          <span className="rounded-full border border-border bg-panel px-2.5 py-0.5 text-[10.5px] font-medium text-text-muted">
            {tag}
          </span>
        )}
      </div>
      {children}
    </div>
  )
}
