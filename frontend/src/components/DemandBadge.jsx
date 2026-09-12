import clsx from 'clsx'

const config = {
  low:    { label: 'Low demand',  dot: 'bg-ink-400',   cls: 'text-ink-500 border-line' },
  medium: { label: 'Normal',      dot: 'bg-sage-500',  cls: 'text-sage-700 border-sage-300' },
  high:   { label: 'High demand', dot: 'bg-flag-warn', cls: 'text-flag-warn border-clay-300' },
  surge:  { label: 'Surge',       dot: 'bg-flag-up',   cls: 'text-flag-up border-flag-up/30', pulse: true },
}

export default function DemandBadge({ level }) {
  if (!level) return null
  const c = config[level] || config.medium
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border bg-paper-50 text-[11px] uppercase tracking-caps whitespace-nowrap',
      c.cls,
    )}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', c.dot, c.pulse && 'animate-pulse')} />
      {c.label}
    </span>
  )
}
