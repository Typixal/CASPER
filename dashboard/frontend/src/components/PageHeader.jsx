/**
 * Page title plus one plain sentence on what the page is for.
 * @param {object} props
 * @param {string} props.title
 */
export default function PageHeader({ title, children }) {
  return (
    <header className="mb-6">
      <h1 className="text-2xl font-bold text-text sm:text-[28px]">{title}</h1>
      {children && <p className="mt-1.5 max-w-3xl text-[15px] leading-relaxed text-text-muted">{children}</p>}
    </header>
  )
}
