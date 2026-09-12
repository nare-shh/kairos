import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Trash2, ArrowRight, Minus, Plus, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import ProductImage from '../components/ProductImage'
import { PageLoader } from '../components/ui'
import { inr } from '../lib/format'

const TAX_RATE = 0.18   // must match the backend (order_service.TAX_RATE)

export default function Cart() {
  const { cart, fetchCart, updateQuantity, removeFromCart } = useCart()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [busyItem, setBusyItem] = useState(null)

  // Always re-read the cart here so prices and stock are live
  useEffect(() => {
    if (!user) { setLoading(false); return }
    fetchCart().finally(() => setLoading(false))
  }, [user, fetchCart])

  const changeQuantity = async (productId, quantity) => {
    setBusyItem(productId)
    if (quantity <= 0) await removeFromCart(productId)
    else await updateQuantity(productId, quantity)
    setBusyItem(null)
  }

  if (!user && !authLoading) return (
    <div className="max-w-xl mx-auto px-5 py-28 text-center">
      <h1 className="display text-4xl mb-3">Your cart is waiting.</h1>
      <p className="text-ink-500 mb-8">Sign in to add items and see live prices.</p>
      <Link to="/auth" state={{ from: '/cart' }} className="btn-primary">Sign in</Link>
    </div>
  )

  if (loading || authLoading) return <PageLoader />

  if (!cart || cart.is_empty) return (
    <div className="max-w-xl mx-auto px-5 py-28 text-center">
      <h1 className="display text-4xl mb-3">Nothing in the cart.</h1>
      <p className="text-ink-500 mb-8">Browse the catalog and add something.</p>
      <Link to="/" className="btn-primary">Browse products</Link>
    </div>
  )

  const subtotal = Number(cart.subtotal)
  const tax = Math.round(subtotal * TAX_RATE * 100) / 100
  const total = subtotal + tax
  const unavailable = cart.items.filter(i => !i.is_in_stock)
  const repriced = cart.items.filter(i => i.price_changed)

  return (
    <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12">
      <p className="eyebrow mb-4">{cart.item_count} item{cart.item_count === 1 ? '' : 's'}</p>
      <h1 className="display text-5xl mb-10">Your cart.</h1>

      {repriced.length > 0 && (
        <p className="mb-8 px-4 py-3 rounded-xl bg-sage-100 border border-sage-300 text-sm text-sage-700">
          Kairos repriced {repriced.length} item{repriced.length > 1 ? 's' : ''} while
          {repriced.length > 1 ? ' they were' : ' it was'} in your cart — you pay the live price below.
        </p>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        {/* Items */}
        <ul className="lg:col-span-2 divide-y divide-line border-y border-line">
          {cart.items.map(item => (
            <li key={item.product_id} className="flex items-center gap-5 py-6">
              <ProductImage product={{ name: item.product_name }} className="w-16 h-16 rounded-xl flex-shrink-0" textClass="text-2xl" />

              <div className="flex-1 min-w-0">
                <p className="eyebrow mb-1">{item.sku}</p>
                <Link to={`/products/${item.product_id}`} className="display text-lg leading-snug hover:text-sage-700 transition-colors line-clamp-1">
                  {item.product_name}
                </Link>
                {!item.is_in_stock && (
                  <p className="text-xs text-flag-up mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    {item.stock_available > 0 ? `Only ${item.stock_available} available` : 'No longer available'}
                  </p>
                )}
              </div>

              <div className="flex items-center border border-line rounded-full overflow-hidden flex-shrink-0">
                <button onClick={() => changeQuantity(item.product_id, item.quantity - 1)} disabled={busyItem === item.product_id}
                  aria-label="Decrease quantity" className="px-2.5 py-1.5 text-ink-500 hover:text-ink hover:bg-paper-200 disabled:opacity-40 transition-colors">
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="w-8 text-center text-xs tabular-nums">{item.quantity}</span>
                <button onClick={() => changeQuantity(item.product_id, item.quantity + 1)}
                  disabled={busyItem === item.product_id || item.quantity >= item.stock_available}
                  aria-label="Increase quantity" className="px-2.5 py-1.5 text-ink-500 hover:text-ink hover:bg-paper-200 disabled:opacity-40 transition-colors">
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="text-right w-28 flex-shrink-0">
                <p className="display text-lg tabular-nums">{inr(item.total_price)}</p>
                <p className="text-xs text-ink-500 tabular-nums">{inr(item.unit_price)} each</p>
                {item.price_changed && (
                  <p className="text-[11px] text-ink-400 line-through tabular-nums">{inr(item.added_unit_price)}</p>
                )}
              </div>

              <button onClick={() => changeQuantity(item.product_id, 0)} aria-label={`Remove ${item.product_name}`}
                className="p-2 rounded-full text-ink-400 hover:text-flag-up hover:bg-paper-200 transition-colors flex-shrink-0">
                <Trash2 className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>

        {/* Summary */}
        <div className="lg:col-span-1">
          <div className="card p-6 sticky top-24">
            <h2 className="eyebrow mb-5">Summary</h2>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between"><dt className="text-ink-500">Subtotal</dt><dd className="tabular-nums">{inr(subtotal)}</dd></div>
              <div className="flex justify-between"><dt className="text-ink-500">Tax (18% GST)</dt><dd className="tabular-nums">{inr(tax)}</dd></div>
              <div className="flex justify-between"><dt className="text-ink-500">Shipping</dt><dd className="text-sage-700">Free</dd></div>
            </dl>
            <div className="flex items-baseline justify-between gap-4 mt-5 pt-5 border-t border-line">
              <span className="eyebrow">Total</span>
              <span className="display text-3xl tabular-nums">{inr(total)}</span>
            </div>

            <button onClick={() => navigate('/checkout')} disabled={unavailable.length > 0}
              className="btn-primary w-full py-3 mt-6">
              Checkout <ArrowRight className="w-4 h-4" />
            </button>
            <p className="text-[11px] text-ink-400 mt-3 leading-relaxed">
              {unavailable.length > 0
                ? 'Remove or reduce unavailable items to continue.'
                : 'These are live Kairos prices. The final price is locked in when you place the order.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
