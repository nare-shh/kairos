import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Receipt, CreditCard, XCircle, Truck, MapPin } from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { errorMessage, ordersAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'
import Modal from '../components/Modal'
import OrderStatusBadge from '../components/OrderStatusBadge'
import PaymentPanel from '../components/PaymentPanel'
import { inputClass, PageLoader, primaryButton, secondaryButton } from '../components/ui'
import { formatDateTime, inr } from '../lib/format'

const PAGE_SIZE = 10
const NEXT_STATUS = { paid: 'processing', processing: 'shipped', shipped: 'delivered' }
const STATUSES = ['pending_payment', 'paid', 'processing', 'shipped', 'delivered', 'cancelled', 'payment_failed']

function OrderCard({ order, adminView, onPay, onCancel, onAdvance }) {
  const address = order.shipping_address || {}
  const next = NEXT_STATUS[order.status]

  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <p className="font-mono font-semibold text-brand-500">{order.order_number}</p>
          <p className="text-xs text-slate-500 mt-0.5">{formatDateTime(order.created_at)}</p>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      <div className="space-y-1.5 mb-4">
        {order.items.map(item => (
          <div key={item.id} className="flex justify-between gap-3 text-sm">
            <Link to={`/products/${item.product_id}`} className="text-slate-300 hover:text-brand-500 truncate">
              {item.quantity} × {item.product_name}
            </Link>
            <span className="tabular-nums text-slate-400 flex-shrink-0">{inr(item.total_price)}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-surface-700">
        <div className="text-xs text-slate-500 flex items-center gap-1.5 min-w-0">
          <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="truncate">{[address.full_name, address.city, address.state].filter(Boolean).join(', ')}</span>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-500 mr-2">Total incl. GST</span>
          <span className="font-bold tabular-nums">{inr(order.total_amount)}</span>
        </div>
      </div>

      {(order.status === 'pending_payment' || (adminView && next)) && (
        <div className="flex flex-wrap gap-2 mt-4">
          {order.status === 'pending_payment' && !adminView && (
            <button onClick={() => onPay(order)} className={primaryButton}>
              <CreditCard className="w-4 h-4" /> Pay now
            </button>
          )}
          {order.status === 'pending_payment' && (
            <button onClick={() => onCancel(order)} className={secondaryButton}>
              <XCircle className="w-4 h-4" /> Cancel order
            </button>
          )}
          {adminView && next && (
            <button onClick={() => onAdvance(order, next)} className={primaryButton}>
              <Truck className="w-4 h-4" /> Mark as {next}
            </button>
          )}
        </div>
      )}
    </div>
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
      toast.success(`${order.order_number} marked as ${next}`)
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
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-8">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Receipt className="w-6 h-6" /> {scope === 'all' ? 'All Orders' : 'Your Orders'}
        </h1>

        {isAdmin && (
          <div className="flex items-center gap-2">
            <div className="flex bg-surface-800 border border-surface-700 rounded-xl p-1">
              {[['mine', 'Mine'], ['all', 'All (admin)']].map(([key, label]) => (
                <button key={key} onClick={() => { setScope(key); setPage(1) }}
                  className={clsx('px-3 py-1.5 text-xs font-medium rounded-lg transition-colors',
                    scope === key ? 'bg-surface-600 text-white' : 'text-slate-400 hover:text-white')}>
                  {label}
                </button>
              ))}
            </div>
            {scope === 'all' && (
              <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1) }}
                aria-label="Filter by status" className={`${inputClass} !w-auto !py-1.5 text-xs`}>
                <option value="">Any status</option>
                {STATUSES.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            )}
          </div>
        )}
      </div>

      {loading && !data ? <PageLoader /> : data?.items.length === 0 ? (
        <div className="text-center py-24 text-slate-500">
          <Receipt className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="mb-6">No orders yet.</p>
          {scope === 'mine' && <Link to="/" className={primaryButton}>Start shopping</Link>}
        </div>
      ) : (
        <div className={clsx('space-y-4 transition-opacity', loading && 'opacity-60')}>
          {data?.items.map(order => (
            <OrderCard key={order.id} order={order} adminView={scope === 'all'}
              onPay={handlePay} onCancel={handleCancel} onAdvance={handleAdvance} />
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="flex justify-center gap-2 mt-8">
          {Array.from({ length: pages }).map((_, i) => (
            <button key={i} onClick={() => setPage(i + 1)}
              className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors
                ${page === i + 1 ? 'bg-brand-600 text-white' : 'bg-surface-700 text-slate-400 hover:bg-surface-600'}`}>
              {i + 1}
            </button>
          ))}
        </div>
      )}

      {paying && (
        <Modal title={`Pay for ${paying.order.order_number}`} onClose={() => setPaying(null)}>
          <div className="flex justify-between items-center mb-5">
            <span className="text-slate-400">Amount due</span>
            <span className="text-xl font-bold tabular-nums">{inr(paying.payment.amount_to_pay)}</span>
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
