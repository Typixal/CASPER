/**
 * Shared shell for the Module A / B / D status cards. Dimmed with a
 * "not built yet" badge until the module's artifacts exist on disk, then
 * switches to a raised card with a green accent and shows whatever detail
 * the caller passes as children.
 */
export default function ModulePanel({ title, module, children }) {
  const built = module?.built

  return (
    <div
      className={
        "rounded-2xl border p-4 " +
        (built
          ? "border-green/30 border-l-4 border-l-green bg-panel-raised shadow-sm"
          : "border-dashed border-border bg-panel/60")
      }
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className={`text-sm font-semibold ${built ? "text-navy" : "text-text-muted"}`}>{title}</h3>
        {!built && (
          <span className="rounded-full border border-dashed border-border px-2.5 py-0.5 text-[11px] text-text-muted">
            not built yet
          </span>
        )}
      </div>

      <div className={`mt-2 text-xs ${built ? "text-text" : "text-text-muted"}`}>{children}</div>
    </div>
  )
}
