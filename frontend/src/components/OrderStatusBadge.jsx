import clsx from 'clsx'

const STYLES = {
  pending_payment: { label: 'Awaiting payment', cls: 'text-flag-warn border-clay-300 bg-clay-100/60' },
  paid:            { label: 'Paid',             cls: 'text-sage-700 border-sage-300 bg-sage-100' },
  processing:      { label: 'Processing',       cls: 'text-ink-700 border-line-strong bg-paper-200' },
  shipped:         { label: 'Shipped',          cls: 'text-ink-700 border-line-strong bg-paper-200' },
  delivered:       { label: 'Delivered',        cls: 'text-paper-50 border-sage-900 bg-sage-900' },
  cancelled:       { label: 'Cancelled',        cls: 'text-ink-500 border-line bg-paper-200' },
  payment_failed:  { label: 'Payment failed',   cls: 'text-flag-up border-flag-up/30 bg-flag-up/5' },
  refunded:        { label: 'Refunded',         cls: 'text-ink-500 border-line bg-paper-200' },
}

export default function OrderStatusBadge({ status }) {
  const s = STYLES[status] || { label: status, cls: 'text-ink-500 border-line bg-paper-200' }
  return (
    <span className={clsx('px-2.5 py-1 rounded-full border text-[11px] uppercase tracking-caps whitespace-nowrap', s.cls)}>
      {s.label}
    </span>
  )
}
