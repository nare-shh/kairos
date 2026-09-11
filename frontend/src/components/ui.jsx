// Shared form + button styles so every page looks the same

export const inputClass =
  'w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors placeholder:text-slate-600 disabled:opacity-60'

export const primaryButton =
  'inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors'

export const secondaryButton =
  'inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-surface-700 hover:bg-surface-600 border border-surface-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium transition-colors'

export function FormField({ label, hint, children }) {
  return (
    <label className="block">
      <span className="block text-xs text-slate-400 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-slate-600 mt-1">{hint}</span>}
    </label>
  )
}

export function Spinner({ className = 'w-4 h-4' }) {
  return <span className={`${className} inline-block border-2 border-white/30 border-t-white rounded-full animate-spin`} />
}

export function PageLoader() {
  return (
    <div className="flex justify-center py-24">
      <Spinner className="w-6 h-6" />
    </div>
  )
}
