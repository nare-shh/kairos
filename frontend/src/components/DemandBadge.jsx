import clsx from 'clsx'

const config = {
  low:    { label: 'Low Demand',    dot: 'bg-slate-400',  bg: 'bg-slate-400/10', text: 'text-slate-400'  },
  medium: { label: 'Normal',        dot: 'bg-emerald-400', bg: 'bg-emerald-400/10', text: 'text-emerald-400' },
  high:   { label: 'High Demand',   dot: 'bg-amber-400',  bg: 'bg-amber-400/10', text: 'text-amber-400'  },
  surge:  { label: '🔥 Surge',      dot: 'bg-red-500',    bg: 'bg-red-500/10',   text: 'text-red-400', pulse: true },
}

export default function DemandBadge({ level }) {
  if (!level) return null
  const c = config[level] || config.medium
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium', c.bg, c.text)}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', c.dot, c.pulse && 'animate-pulse')} />
      {c.label}
    </span>
  )
}
