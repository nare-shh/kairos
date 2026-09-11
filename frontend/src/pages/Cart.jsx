import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShoppingCart, Trash2, ArrowRight, Package, Minus, Plus, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import ProductImage from '../components/ProductImage'
import { inr } from '../lib/format'

const TAX_RATE = 0.18   // must match the backend (order_service.TAX_RATE)

export default function Cart() {
  const { cart, fetchCart, updateQuantity, removeFromCart } = useCart()
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [busyItem, setBusyItem] = useState(null)

  // Always re-read the cart here so prices/stock are live
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
    <div className="max-w-2xl mx-auto px-4 py-24 text-center">
      <ShoppingCart className="w-12 h-12 mx-auto mb-4 text-slate-600" />
      <h2 className="text-xl font-semibold mb-2">Sign in to view your cart</h2>
      <p className="text-slate-500 mb-6">You need to be logged in to add items to your cart.</p>
      <Link to="/auth" state={{ from: '/cart' }} className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
        Sign in
      </Link>
    </div>
  )

  if (loading || authLoading) return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      {[...Array(3)].map((_, i) => <div key={i} className="h-20 bg-surface-700 rounded-xl mb-3 animate-pulse" />)}
    </div>
  )

  if (!cart || cart.is_empty) return (
    <div className="max-w-2xl mx-auto px-4 py-24 text-center">
      <Package className="w-12 h-12 mx-auto mb-4 text-slate-600" />
      <h2 className="text-xl font-semibold mb-2">Your cart is empty</h2>
      <p className="text-slate-500 mb-6">Add some products to get started.</p>
      <Link to="/" className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
        Browse Products
      </Link>
    </div>
  )

  const subtotal = Number(cart.subtotal)
  const tax = Math.round(subtotal * TAX_RATE * 100) / 100
  const total = subtotal + tax
  const unavailable = cart.items.filter(i => !i.is_in_stock)
  const repriced = cart.items.filter(i => i.price_changed)

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <h1 className="text-2xl font-bold mb-8 flex items-center gap-2">
        <ShoppingCart className="w-6 h-6" /> Cart
        <span className="text-sm font-normal text-slate-500">({cart.item_count} items)</span>
      </h1>

      {repriced.length > 0 && (
        <div className="mb-4 p-3 rounded-xl bg-brand-600/10 border border-brand-600/20 text-sm text-brand-500">
          ⚡ Kairos repriced {repriced.length} item{repriced.length > 1 ? 's' : ''} since you added {repriced.length > 1 ? 'them' : 'it'} —
          you'll pay the live price shown below.
        </div>
      )}

      {/* Items */}
      <div className="space-y-3 mb-8">
        {cart.items.map(item => (
          <div key={item.product_id}
            className={clsx('flex items-center gap-4 p-4 bg-surface-800 border rounded-xl',
              item.is_in_stock ? 'border-surface-700' : 'border-red-500/30')}>
            <ProductImage product={{ name: item.product_name }} className="w-12 h-12 rounded-lg flex-shrink-0" textClass="text-lg" />
            <div className="flex-1 min-w-0">
              <Link to={`/products/${item.product_id}`} className="font-medium text-sm truncate block hover:text-brand-500">
                {item.product_name}
              </Link>
              <p className="text-xs text-slate-500">{item.sku}</p>
              {!item.is_in_stock && (
                <p className="text-xs text-red-400 mt-0.5 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  {item.stock_available > 0 ? `Only ${item.stock_available} available` : 'No longer available'}
                </p>
              )}
            </div>

            <div className="flex items-center bg-surface-700 border border-surface-600 rounded-lg overflow-hidden flex-shrink-0">
              <button onClick={() => changeQuantity(item.product_id, item.quantity - 1)} disabled={busyItem === item.product_id}
                aria-label="Decrease quantity" className="px-2 py-1.5 hover:bg-surface-600 disabled:opacity-40">
                <Minus className="w-3.5 h-3.5" />
              </button>
              <span className="w-7 text-center text-xs font-semibold">{item.quantity}</span>
              <button onClick={() => changeQuantity(item.product_id, item.quantity + 1)}
                disabled={busyItem === item.product_id || item.quantity >= item.stock_available}
                aria-label="Increase quantity" className="px-2 py-1.5 hover:bg-surface-600 disabled:opacity-40">
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="text-right flex-shrink-0 w-24">
              <p className="text-sm font-semibold tabular-nums">{inr(item.total_price)}</p>
              <p className="text-xs text-slate-500 tabular-nums">
                {inr(item.unit_price)} each
              </p>
              {item.price_changed && (
                <p className="text-[11px] text-slate-600 line-through tabular-nums">{inr(item.added_unit_price)}</p>
              )}
            </div>
            <button onClick={() => changeQuantity(item.product_id, 0)} aria-label={`Remove ${item.product_name}`}
              className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-colors flex-shrink-0">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Subtotal</span>
          <span className="tabular-nums">{inr(subtotal)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Tax (18% GST)</span>
          <span className="tabular-nums">{inr(tax)}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Shipping</span>
          <span className="text-emerald-400">Free</span>
        </div>
        <div className="pt-3 border-t border-surface-700 flex justify-between font-bold text-lg">
          <span>Total</span>
          <span className="tabular-nums">{inr(total)}</span>
        </div>

        <button
          onClick={() => navigate('/checkout')}
          disabled={unavailable.length > 0}
          className="w-full flex items-center justify-center gap-2 py-3 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl font-medium transition-colors mt-2">
          Proceed to Checkout
          <ArrowRight className="w-4 h-4" />
        </button>
        <p className="text-xs text-center text-slate-600">
          {unavailable.length > 0
            ? 'Remove or reduce unavailable items to continue.'
            : 'Prices are live Kairos prices — the final price is locked in when you place the order.'}
        </p>
      </div>
    </div>
  )
}
