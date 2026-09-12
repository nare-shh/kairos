import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CreditCard, XCircle, Truck, MapPin } from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { errorMessage, ordersAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import OrderStatusBadge from '../components/OrderStatusBadge'
import PaymentPanel from '../components/PaymentPanel'
import { PageLoader, inputClass } from '../components/ui'
import { formatDateTime, inr } from '../lib/format'

const PAGE_SIZE = 10
const NEXT_STATUS = { paid: 'processing', processing: 'shipped', shipped: 'delivered' }
const STATUSES = ['pending_payment', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'payment_failed']

function OrderCard({ order, adminView, onPay, onCancel, onAdvance }) {
  const address = order.shipping_address || {}
  const next = NEXT_STATUS[order.status]

  return (
    <article className="card p-6">
      <div className="flex flex-wrap items-start justify-between gap-4 pb-5 border-b border-line">
        <div>
          <p className="font-mono text-sm text-ink-700">{order.order_number}</p>
          <p className="eyebrow mt-1.5">{formatDateTime(order.created_at)}</p>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      <ul className="divide-y divide-line">
        {order.items.map(item => (
          <li key={item.id} className="flex justify-between gap-4 py-3.5 text-sm">
            <Link to={`/products/${item.product_id}`} className="text-ink-700 hover:text-sage-700 transition-colors truncate">
              {item.quantity} × {item.product_name}
            </Link>
            <span className="tabular-nums text-ink-500 flex-shrink-0">{inr(item.total_price)}</span>
          </li>
        ))}
      </ul>

      <div className="flex flex-wrap items-end justify-between gap-4 pt-5 border-t border-line">
        <p className="text-xs text-ink-500 flex items-center gap-1.5 min-w-0">
          <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate">{[address.full_name, address.city, address.state].filter(Boolean).join(', ')}</span>
        </p>
        <div className="text-right">
          <p className="eyebrow">Total incl. GST</p>
          <p className="display text-2xl tabular-nums">{inr(order.total_amount)}</p>
        </div>
      </div>

      {(order.status === 'pending_payment' || (adminView && next)) && (
        <div className="flex flex-wrap gap-3 mt-6">
          {order.status === 'pending_payment' && !adminView && (
            <button onClick={() => onPay(order)} className="btn-primary">
              <CreditCard className="w-4 h-4" /> Pay now
            </button>
          )}
          {order.status === 'pending_payment' && (
            <button onClick={() => onCancel(order)} className="btn-ghost">
              <XCircle className="w-4 h-4" /> Cancel
            </button>
          )}
          {adminView && next && (
            <button onClick={() => onAdvance(order, next)} className="btn-primary">
              <Truck className="w-4 h-4" /> Mark {next}
            </button>
          )}
        </div>
      )}
    </article>
  )
}

export default function Orders() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [scope,        setScope]        = useState('mine')   // mine | all (admin)
  const [statusFilter, setStatusFilter] = useState('')
  const [page,         setPage]         = useState(1)
  const [data,         setData]         = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [paying,       setPaying]       = useState(null)     // { order, payment }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      const res = scope === 'all'
        ? await ordersAPI.all({ ...params, ...(statusFilter && { status: statusFilter }) })
        : await ordersAPI.list(params)
      setData(res.data)
    } catch (e) {
      toast.error(errorMessage(e, 'Could not load orders'))
    } finally {
      setLoading(false)
    }
  }, [scope, statusFilter, page])

  useEffect(() => { load() }, [load])

  const replace = (order) =>
    setData(d => d && ({ ...d, items: d.items.map(o => (o.id === order.id ? order : o)) }))

  const handlePay = async (order) => {
    try {
      const { data: payment } = await ordersAPI.payment(order.id)
      setPaying({ order, payment })
    } catch (e) {
      toast.error(errorMessage(e))
      load()
    }
  }

  const handleCancel = async (order) => {
    if (!window.confirm(`Cancel order ${order.order_number}? Its items go back into stock.`)) return
    try {
      const { data: updated } = await ordersAPI.cancel(order.id)
      replace(updated)
      toast.success('Order cancelled')
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const handleAdvance = async (order, next) => {
    try {
      const { data: updated } = await ordersAPI.setStatus(order.id, next)
      replace(updated)
      toast.success(`${order.order_number} marked ${next}`)
    } catch (e) {
      toast.error(errorMessage(e))
    }
  }

  const handlePaid = (order) => {
    if (order) replace(order)
    else load()
    setPaying(null)
    toast.success('Payment complete')
  }

  const pages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <div className="max-w-3xl mx-auto px-5 sm:px-8 py-12">
      <p className="eyebrow mb-4">{scope === 'all' ? 'Every order' : 'Your history'}</p>
      <h1 className="display text-5xl mb-10">Orders.</h1>

      {isAdmin && (
        <div className="flex flex-wrap items-center justify-between gap-4 mb-10 pb-3 border-b border-line">
          <div className="flex gap-6">
            {[['mine', 'Mine'], ['all', 'All orders']].map(([key, label]) => (
              <button key={key} onClick={() => { setScope(key); setPage(1) }}
                className={clsx('pb-3 -mb-px text-sm border-b transition-colors',
                  scope === key ? 'border-ink text-ink' : 'border-transparent text-ink-500 hover:text-ink')}>
                {label}
              </button>
            ))}
          </div>
          {scope === 'all' && (
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
              aria-label="Filter by status" className={`${inputClass} w-auto py-1.5 text-xs`}>
              <option value="">Any status</option>
              {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
          )}
        </div>
      )}

      {loading && !data ? <PageLoader /> : data?.items.length === 0 ? (
        <div className="text-center py-24">
          <p className="display text-3xl mb-3">No orders yet.</p>
          {scope === 'mine' && <Link to="/" className="btn-primary mt-4">Start shopping</Link>}
        </div>
      ) : (
        <div className={clsx('space-y-6 transition-opacity', loading && 'opacity-60')}>
          {data?.items.map(order => (
            <OrderCard key={order.id} order={order} adminView={scope === 'all'}
              onPay={handlePay} onCancel={handleCancel} onAdvance={handleAdvance} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="flex justify-center gap-2 mt-12">
          {Array.from({ length: pages }).map((_, i) => (
            <button key={i} onClick={() => setPage(i + 1)}
              className={clsx('w-9 h-9 rounded-full border text-sm transition-colors',
                page === i + 1 ? 'bg-sage-900 border-sage-900 text-paper-50' : 'border-line text-ink-500 hover:text-ink')}>
              {i + 1}
            </button>
          ))}
        </div>
      )}

      {paying && (
        <Modal title={`Pay ${paying.order.order_number}`} onClose={() => setPaying(null)}>
          <div className="flex items-baseline justify-between gap-4 pb-5 mb-6 border-b border-line">
            <span className="eyebrow">Amount due</span>
            <span className="display text-3xl tabular-nums">{inr(paying.payment.amount_to_pay)}</span>
          </div>
          <PaymentPanel
            orderId={paying.order.id}
            clientSecret={paying.payment.client_secret}
            amount={paying.payment.amount_to_pay}
            mock={paying.payment.mock_payment}
            onPaid={handlePaid}
          />
        </Modal>
      )}
    </div>
  )
}
