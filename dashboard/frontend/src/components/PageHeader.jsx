/**
 * Every page opens with a title and one plain sentence saying what the page
 * is for -- so a viewer who wandered in mid-demo is never lost.
 */
export default function PageHeader({ title, children }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-bold text-text sm:text-[28px]">{title}</h1>
      {children && <p className="mt-1.5 max-w-3xl text-[15px] leading-relaxed text-text-muted">{children}</p>}
    </header>
  )
}
