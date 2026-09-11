import clsx from 'clsx'

const STYLES = {
  pending_payment: { label: 'Awaiting payment', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  paid:            { label: 'Paid',             cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
  processing:      { label: 'Processing',       cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
  shipped:         { label: 'Shipped',          cls: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20' },
  delivered:       { label: 'Delivered',        cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  cancelled:       { label: 'Cancelled',        cls: 'bg-slate-500/10 text-slate-400 border-slate-500/20' },
  payment_failed:  { label: 'Payment failed',   cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
  refunded:        { label: 'Refunded',         cls: 'bg-slate-500/10 text-slate-300 border-slate-500/20' },
}

export default function OrderStatusBadge({ status }) {
  const s = STYLES[status] || { label: status, cls: 'bg-slate-500/10 text-slate-400 border-slate-500/20' }
  return (
    <span className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border whitespace-nowrap', s.cls)}>
      {s.label}
    </span>
  )
}
