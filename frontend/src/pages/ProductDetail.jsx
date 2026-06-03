import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ShoppingCart, TrendingUp, TrendingDown, Minus, Plus, Eye, Clock } from 'lucide-react'
import clsx from 'clsx'
import { productsAPI, intentAPI } from '../api/client'
import { useLivePrice } from '../hooks/useLivePrice'
import DemandBadge from '../components/DemandBadge'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'

const GRADIENTS = [
  'from-violet-600 to-indigo-600', 'from-blue-600 to-cyan-600',
  'from-emerald-600 to-teal-600',  'from-orange-600 to-amber-600',
  'from-pink-600 to-rose-600',     'from-purple-600 to-pink-600',
]

export default function ProductDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const { addToCart } = useCart()

  const [product,  setProduct]  = useState(null)
  const [quantity, setQuantity] = useState(1)
  const [events,   setEvents]   = useState([])
  const [loading,  setLoading]  = useState(true)
  const [score,    setScore]    = useState(null)

  const { price, demand, flashing } = useLivePrice(id, product?.current_price)

  // Load product
  useEffect(() => {
    if (!id) return
    productsAPI.get(id)
      .then(r => setProduct(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  // Track view intent
  useEffect(() => {
    if (!id) return
    intentAPI.track({ product_id: id, event_type: 'ProductViewed', session_id: `sess-${Date.now()}` })
      .catch(() => {})
  }, [id])

  // Fetch price history events (seller/admin only)
  useEffect(() => {
    if (!id || !user) return
    productsAPI.events(id).then(r => setEvents(r.data)).catch(() => {})
  }, [id, user])

  if (loading) return (
    <div className="max-w-5xl mx-auto px-4 py-16 animate-pulse">
      <div className="h-6 bg-surface-700 rounded w-32 mb-8" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
        <div className="h-96 bg-surface-700 rounded-2xl" />
        <div className="space-y-4">
          {[...Array(5)].map((_, i) => <div key={i} className="h-6 bg-surface-700 rounded" />)}
        </div>
      </div>
    </div>
  )

  if (!product) return (
    <div className="text-center py-24 text-slate-500">Product not found.</div>
  )

  const gradIdx = product.name.charCodeAt(0) % GRADIENTS.length
  const currentPrice = price ?? parseFloat(product.current_price)
  const basePrice    = parseFloat(product.base_price)
  const isSurge      = currentPrice > basePrice
  const isOnSale     = currentPrice < basePrice
  const priceDiff    = ((currentPrice - basePrice) / basePrice * 100).toFixed(1)
  const activeDemand = demand || null

  const handleAddToCart = () => {
    intentAPI.track({ product_id: id, event_type: 'CartAdded', session_id: `sess-${Date.now()}` }).catch(() => {})
    addToCart(product.id, quantity)
  }

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-slide-up">

      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to products
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">

        {/* Image */}
        <div className={clsx('h-80 md:h-full min-h-64 rounded-2xl bg-gradient-to-br flex items-center justify-center', GRADIENTS[gradIdx])}>
          <span className="text-8xl font-black text-white/20 select-none">{product.name[0].toUpperCase()}</span>
        </div>

        {/* Info */}
        <div className="flex flex-col gap-5">

          <div>
            <div className="flex items-start justify-between gap-2 mb-1">
              <h1 className="text-2xl font-bold leading-tight">{product.name}</h1>
              {activeDemand && <DemandBadge level={activeDemand} />}
            </div>
            <p className="text-sm text-slate-500">SKU: {product.sku}</p>
          </div>

          {/* Live Price */}
          <div className="bg-surface-700 rounded-xl p-4 border border-surface-600">
            <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Current Price</p>
            <div className="flex items-baseline gap-3">
              <span className={clsx(
                'text-4xl font-extrabold tabular-nums transition-all duration-300',
                flashing && 'text-emerald-400 scale-110',
                isSurge && !flashing && 'text-red-400',
                isOnSale && !flashing && 'text-emerald-400',
                !isSurge && !isOnSale && !flashing && 'text-white',
              )}>
                ₹{currentPrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
              {(isSurge || isOnSale) && (
                <div className="flex flex-col">
                  <span className="text-sm text-slate-500 line-through tabular-nums">
                    ₹{basePrice.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                  <span className={clsx('text-xs font-semibold flex items-center gap-0.5', isSurge ? 'text-red-400' : 'text-emerald-400')}>
                    {isSurge ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {isSurge ? '+' : ''}{priceDiff}% vs base
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-1.5 mt-2">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-xs text-slate-500">Live pricing active — updates in real-time</span>
            </div>
          </div>

          {/* Stock */}
          <div className="flex items-center gap-2 text-sm">
            <span className={clsx('font-medium', product.stock_quantity > 0 ? 'text-emerald-400' : 'text-red-400')}>
              {product.stock_quantity > 0 ? `✓ ${product.stock_quantity} units in stock` : '✗ Out of stock'}
            </span>
            {product.stock_quantity <= product.low_stock_threshold && product.stock_quantity > 0 && (
              <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 text-xs rounded-full border border-amber-500/20">
                Only {product.stock_quantity} left!
              </span>
            )}
          </div>

          {/* Description */}
          {product.description && (
            <p className="text-sm text-slate-400 leading-relaxed">{product.description}</p>
          )}

          {/* Attributes */}
          {Object.keys(product.attributes).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(product.attributes).map(([k, v]) => (
                <span key={k} className="px-2.5 py-1 bg-surface-700 rounded-lg text-xs text-slate-400 border border-surface-600">
                  <span className="text-slate-500">{k}:</span> {v}
                </span>
              ))}
            </div>
          )}

          {/* Quantity + Add to Cart */}
          <div className="flex items-center gap-3 mt-2">
            <div className="flex items-center gap-0 bg-surface-700 border border-surface-600 rounded-xl overflow-hidden">
              <button onClick={() => setQuantity(q => Math.max(1, q - 1))}
                className="px-3 py-2.5 hover:bg-surface-600 transition-colors">
                <Minus className="w-4 h-4" />
              </button>
              <span className="w-10 text-center text-sm font-semibold">{quantity}</span>
              <button onClick={() => setQuantity(q => Math.min(product.stock_quantity, q + 1))}
                className="px-3 py-2.5 hover:bg-surface-600 transition-colors">
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <button
              onClick={handleAddToCart}
              disabled={product.stock_quantity === 0}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl font-medium transition-colors">
              <ShoppingCart className="w-4 h-4" />
              Add to Cart · ₹{(currentPrice * quantity).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </button>
          </div>

        </div>
      </div>

      {/* Event History (logged-in users) */}
      {user && events.length > 0 && (
        <section className="mt-14">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Price History (Event Log)
          </h2>
          <div className="space-y-2">
            {events.filter(e => e.event_type === 'ProductPriceChanged').slice(0, 10).map(e => (
              <div key={e.id} className="flex items-center gap-3 p-3 bg-surface-800 border border-surface-700 rounded-xl text-sm">
                <span className={clsx(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  e.caused_by === 'kairos_pricing_engine'
                    ? 'bg-brand-600/20 text-brand-500 border border-brand-600/20'
                    : 'bg-slate-700 text-slate-400'
                )}>
                  {e.caused_by === 'kairos_pricing_engine' ? '⚡ Kairos' : '👤 Manual'}
                </span>
                <span className="text-slate-300 tabular-nums">
                  ₹{e.payload?.old_price} → ₹{e.payload?.new_price}
                </span>
                {e.payload?.demand_level && (
                  <DemandBadge level={e.payload.demand_level} />
                )}
                {e.payload?.reason && (
                  <span className="text-slate-500 text-xs flex-1 truncate">{e.payload.reason}</span>
                )}
                <span className="text-slate-600 text-xs ml-auto whitespace-nowrap">
                  {new Date(e.occurred_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  )
}
