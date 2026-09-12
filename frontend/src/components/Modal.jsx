import { useEffect } from 'react'
import { X } from 'lucide-react'

export default function Modal({ title, onClose, children, wide = false }) {
  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start sm:items-center justify-center p-4 bg-ink/30 backdrop-blur-sm overflow-y-auto"
      onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`w-full ${wide ? 'max-w-3xl' : 'max-w-lg'} my-8 bg-paper-50 border border-line rounded-2xl shadow-xl shadow-ink/5 animate-slide-up`}
      >
        <div className="flex items-center justify-between gap-4 px-6 py-4 border-b border-line">
          <h2 className="display text-xl">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="btn-quiet">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}
