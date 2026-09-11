import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, ShoppingCart, TrendingUp, TrendingDown, Minus, Plus, Clock } from 'lucide-react'
import clsx from 'clsx'
import { errorMessage, productsAPI, trackIntent } from '../api/client'
import { useLivePrice } from '../hooks/useLivePrice'
import DemandBadge from '../components/DemandBadge'
import ProductImage from '../components/ProductImage'
import { useCart } from '../context/CartContext'
import { inr, percentChange } from '../lib/format'

export default function ProductDetail() {
  const { id } = useParams()
  const { addToCart } = useCart()

  const [product,  setProduct]  = useState(null)
  const [quantity, setQuantity] = useState(1)
  const [history,  setHistory]  = useState([])
  const [loading,  setLoading]  = useState(true)
  const [loadError, setLoadError] = useState(null)
  const viewTracked = useRef(null)

  const { price, demand, flashing, connected, applyUpdate } = useLivePrice(id, product?.current_price)

  // Load product
  useEffect(() => {
    if (!id) return
    setLoading(true)
    setQuantity(1)
    productsAPI.get(id)
      .then(r => { setProduct(r.data); setLoadError(null) })
      .catch(err => {
        setProduct(null)
        setLoadError(err.response?.status === 404 ? null : errorMessage(err))
      })
      .finally(() => setLoading(false))
  }, [id])

  // Track the view once per product (the ref survives React StrictMode's double effect).
  // The response carries the re-scored price — apply it in case the view itself moved it.
  useEffect(() => {
    if (!id || viewTracked.current === id) return
    viewTracked.current = id
    trackIntent(id, 'ProductViewed').then(res => {
      if (res?.data) applyUpdate(res.data.current_price, res.data.demand_level)
    })
  }, [id, applyUpdate])

  // Public price history — refreshed whenever a live price update arrives
  useEffect(() => {
    if (!id) return
    productsAPI.priceHistory(id).then(r => setHistory(r.data)).catch(() => setHistory([]))
  }, [id, price])

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
    <div className="text-center py-24 text-slate-500">
      <p className="mb-4">{loadError || 'Product not found.'}</p>
      <Link to="/" className="text-brand-500 hover:underline">Back to products</Link>
    </div>
  )

  const currentPrice = price ?? Number(product.current_price)
  const basePrice    = Number(product.base_price)
  const isSurge      = currentPrice > basePrice
  const isOnSale     = currentPrice < basePrice
  const priceDiff    = percentChange(currentPrice, basePrice).toFixed(1)
  const inStock      = product.stock_quantity > 0
  const lowStock     = inStock && product.stock_quantity <= product.low_stock_threshold

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-slide-up">

      {/* Back */}
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to products
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-10">

        {/* Image */}
        <ProductImage product={product} className="h-80 md:h-full min-h-64 w-full rounded-2xl" textClass="text-8xl" />

        {/* Info */}
        <div className="flex flex-col gap-5">

          <div>
            <div className="flex items-start justify-between gap-2 mb-1">
              <h1 className="text-2xl font-bold leading-tight">{product.name}</h1>
              {demand && <DemandBadge level={demand} />}
            </div>
            <p className="text-sm text-slate-500">SKU: {product.sku}</p>
          </div>

          {/* Live Price */}
          <div className="bg-surface-700 rounded-xl p-4 border border-surface-600">
            <p className="text-xs text-slate-500 mb-1 uppercase tracking-wider">Current Price</p>
            <div className="flex items-baseline gap-3">
              <span className={clsx(
                'text-4xl font-extrabold tabular-nums transition-all duration-300 inline-block',
                flashing && 'text-emerald-400 scale-110',
                isSurge && !flashing && 'text-red-400',
                isOnSale && !flashing && 'text-emerald-400',
                !isSurge && !isOnSale && !flashing && 'text-white',
              )}>
                {inr(currentPrice)}
              </span>
              {(isSurge || isOnSale) && (
                <div className="flex flex-col">
                  <span className="text-sm text-slate-500 line-through tabular-nums">{inr(basePrice)}</span>
                  <span className={clsx('text-xs font-semibold flex items-center gap-0.5', isSurge ? 'text-red-400' : 'text-emerald-400')}>
                    {isSurge ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {isSurge ? '+' : ''}{priceDiff}% vs base
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-1.5 mt-2">
              <span className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600')} />
              <span className="text-xs text-slate-500">
                {connected ? 'Live pricing active — updates in real-time' : 'Connecting to live pricing…'}
              </span>
            </div>
          </div>

          {/* Stock */}
          <div className="flex items-center gap-2 text-sm">
            <span className={clsx('font-medium', inStock ? 'text-emerald-400' : 'text-red-400')}>
              {inStock ? `✓ ${product.stock_quantity} units in stock` : '✗ Out of stock'}
            </span>
            {lowStock && (
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
          {Object.keys(product.attributes || {}).length > 0 && (
            <div className="flex flex-wrap gap-2">
              {Object.entries(product.attributes).map(([k, v]) => (
                <span key={k} className="px-2.5 py-1 bg-surface-700 rounded-lg text-xs text-slate-400 border border-surface-600">
                  <span className="text-slate-500">{k}:</span> {String(v)}
                </span>
              ))}
            </div>
          )}

          {/* Quantity + Add to Cart */}
          <div className="flex items-center gap-3 mt-2">
            <div className="flex items-center gap-0 bg-surface-700 border border-surface-600 rounded-xl overflow-hidden">
              <button onClick={() => setQuantity(q => Math.max(1, q - 1))} disabled={!inStock} aria-label="Decrease quantity"
                className="px-3 py-2.5 hover:bg-surface-600 disabled:opacity-40 transition-colors">
                <Minus className="w-4 h-4" />
              </button>
              <span className="w-10 text-center text-sm font-semibold">{inStock ? quantity : 0}</span>
              <button onClick={() => setQuantity(q => Math.min(product.stock_quantity, q + 1))} disabled={!inStock} aria-label="Increase quantity"
                className="px-3 py-2.5 hover:bg-surface-600 disabled:opacity-40 transition-colors">
                <Plus className="w-4 h-4" />
              </button>
            </div>

            <button
              onClick={() => addToCart(product.id, quantity)}
              disabled={!inStock}
              className="flex-1 flex items-center justify-center gap-2 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl font-medium transition-colors">
              <ShoppingCart className="w-4 h-4" />
              Add to Cart · {inr(currentPrice * quantity)}
            </button>
          </div>

        </div>
      </div>

      {/* Price History (public event log) */}
      {history.length > 0 && (
        <section className="mt-14">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4" /> Price History
          </h2>
          <div className="space-y-2">
            {history.slice(0, 10).map((h, i) => (
              <div key={`${h.occurred_at}-${i}`} className="flex flex-wrap items-center gap-3 p-3 bg-surface-800 border border-surface-700 rounded-xl text-sm">
                <span className={clsx(
                  'px-2 py-0.5 rounded text-xs font-medium',
                  h.kind === 'dynamic'
                    ? 'bg-brand-600/20 text-brand-500 border border-brand-600/20'
                    : 'bg-slate-700 text-slate-400'
                )}>
                  {h.kind === 'dynamic' ? '⚡ Kairos' : '👤 Seller'}
                </span>
                <span className="text-slate-300 tabular-nums">
                  {inr(h.old_price)} → {inr(h.new_price)}
                </span>
                {h.kind === 'base' && <span className="text-slate-500 text-xs">base price changed</span>}
                {h.demand_level && <DemandBadge level={h.demand_level} />}
                <span className="text-slate-600 text-xs ml-auto whitespace-nowrap">
                  {new Date(h.occurred_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

    </div>
  )
}
