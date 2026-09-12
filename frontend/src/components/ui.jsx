// Shared styles so every page speaks the same visual language.
// The class definitions live in index.css (@layer components).

export const inputClass = 'input'
export const primaryButton = 'btn-primary'
export const secondaryButton = 'btn-ghost'

export function FormField({ label, hint, children }) {
  return (
    <label className="block">
      <span className="block eyebrow mb-1.5">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-ink-400 mt-1.5">{hint}</span>}
    </label>
  )
}

export function Spinner({ className = 'w-4 h-4', tone = 'light' }) {
  const colors = tone === 'dark'
    ? 'border-ink/25 border-t-ink'
    : 'border-paper-50/40 border-t-paper-50'
  return <span className={`${className} ${colors} inline-block border-2 rounded-full animate-spin`} />
}

export function PageLoader() {
  return (
    <div className="flex justify-center py-24">
      <Spinner className="w-6 h-6" tone="dark" />
    </div>
  )
}
