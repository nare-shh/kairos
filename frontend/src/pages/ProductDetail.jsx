import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Minus, Plus, TrendingUp, TrendingDown } from 'lucide-react'
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
    <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16 animate-pulse">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-14">
        <div className="aspect-[4/5] rounded-2xl bg-paper-200" />
        <div className="space-y-5 pt-6">
          {[...Array(6)].map((_, i) => <div key={i} className="h-5 bg-paper-200 rounded" />)}
        </div>
      </div>
    </div>
  )

  if (!product) return (
    <div className="max-w-2xl mx-auto px-5 py-28 text-center">
      <h1 className="display text-4xl mb-3">{loadError ? 'Something went wrong.' : 'Product not found.'}</h1>
      {loadError && <p className="text-ink-500 mb-6">{loadError}</p>}
      <Link to="/" className="btn-ghost">Back to products</Link>
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
    <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12 animate-slide-up">
      <Link to="/" className="inline-flex items-center gap-2 eyebrow mb-10 hover:text-ink transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> All products
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 lg:gap-16">
        {/* Image */}
        <ProductImage product={product} className="w-full aspect-[4/5] rounded-2xl" textClass="text-8xl" />

        {/* Details */}
        <div className="flex flex-col">
          <div className="flex items-start justify-between gap-4">
            <p className="eyebrow">{product.sku}</p>
            {demand && <DemandBadge level={demand} />}
          </div>

          <h1 className="display text-4xl sm:text-5xl leading-[1.05] mt-4">{product.name}</h1>

          {/* Live price */}
          <div className="mt-8 pb-6 border-b border-line">
            <p className="eyebrow mb-3">Current price</p>
            <div className="flex flex-wrap items-baseline gap-4">
              <span className={clsx(
                'display text-5xl tabular-nums transition-all duration-300 inline-block',
                flashing && 'text-sage-600 scale-105',
                isSurge && !flashing && 'text-flag-up',
                isOnSale && !flashing && 'text-sage-700',
              )}>
                {inr(currentPrice)}
              </span>
              {(isSurge || isOnSale) && (
                <span className="flex items-center gap-2 text-sm">
                  <span className="text-ink-400 line-through tabular-nums">{inr(basePrice)}</span>
                  <span className={clsx('inline-flex items-center gap-1', isSurge ? 'text-flag-up' : 'text-sage-700')}>
                    {isSurge ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                    {isSurge ? '+' : ''}{priceDiff}% vs base
                  </span>
                </span>
              )}
            </div>
            <p className="flex items-center gap-2 mt-4 text-xs text-ink-500">
              <span className={clsx('w-1.5 h-1.5 rounded-full', connected ? 'bg-sage-500 animate-pulse' : 'bg-ink-400')} />
              {connected ? 'Live — this price updates as demand changes' : 'Connecting to live pricing…'}
            </p>
          </div>

          {/* Meta rows */}
          <dl className="divide-y divide-line border-b border-line">
            <div className="flex items-center justify-between gap-4 py-3.5">
              <dt className="eyebrow">Availability</dt>
              <dd className={clsx('text-sm', inStock ? 'text-ink' : 'text-flag-up')}>
                {inStock ? `${product.stock_quantity} in stock` : 'Out of stock'}
                {lowStock && <span className="text-flag-warn"> · only {product.stock_quantity} left</span>}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-4 py-3.5">
              <dt className="eyebrow">Price range</dt>
              <dd className="text-sm tabular-nums text-ink-700">{inr(product.min_price)} – {inr(product.max_price)}</dd>
            </div>
            {Object.entries(product.attributes || {}).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between gap-4 py-3.5">
                <dt className="eyebrow">{k}</dt>
                <dd className="text-sm text-ink-700">{String(v)}</dd>
              </div>
            ))}
          </dl>

          {product.description && (
            <p className="text-ink-500 leading-relaxed mt-6">{product.description}</p>
          )}

          {/* Quantity + add to cart */}
          <div className="flex items-center gap-3 mt-8">
            <div className="flex items-center border border-line rounded-full overflow-hidden">
              <button onClick={() => setQuantity(q => Math.max(1, q - 1))} disabled={!inStock}
                aria-label="Decrease quantity"
                className="px-3.5 py-2.5 text-ink-500 hover:text-ink hover:bg-paper-200 disabled:opacity-40 transition-colors">
                <Minus className="w-4 h-4" />
              </button>
              <span className="w-10 text-center text-sm tabular-nums">{inStock ? quantity : 0}</span>
              <button onClick={() => setQuantity(q => Math.min(product.stock_quantity, q + 1))} disabled={!inStock}
                aria-label="Increase quantity"
                className="px-3.5 py-2.5 text-ink-500 hover:text-ink hover:bg-paper-200 disabled:opacity-40 transition-colors">
                <Plus className="w-4 h-4" />
              </button>
            </div>
            <button onClick={() => addToCart(product.id, quantity)} disabled={!inStock}
              className="btn-primary flex-1 py-3">
              Add to cart · {inr(currentPrice * quantity)}
            </button>
          </div>
        </div>
      </div>

      {/* Price history — the public audit trail */}
      {history.length > 0 && (
        <section className="mt-24">
          <div className="flex items-baseline gap-3 pb-3 border-b border-line-strong">
            <h2 className="display text-3xl">Price history</h2>
            <span className="eyebrow">Every change, and what caused it</span>
          </div>
          <ol className="divide-y divide-line">
            {history.slice(0, 10).map((h, i) => (
              <li key={`${h.occurred_at}-${i}`} className="flex flex-wrap items-center gap-x-6 gap-y-2 py-5">
                <span className="eyebrow w-8 flex-shrink-0">{String(i + 1).padStart(2, '0')}</span>
                <span className="display text-xl tabular-nums">
                  {inr(h.old_price)} <span className="text-ink-400">&rarr;</span> {inr(h.new_price)}
                </span>
                <span className={clsx('text-[11px] uppercase tracking-caps px-2 py-0.5 rounded-full border',
                  h.kind === 'dynamic' ? 'border-sage-300 text-sage-700 bg-sage-100' : 'border-line text-ink-500')}>
                  {h.kind === 'dynamic' ? 'Kairos engine' : 'Seller'}
                </span>
                {h.demand_level && <DemandBadge level={h.demand_level} />}
                <span className="text-xs text-ink-400 ml-auto whitespace-nowrap">
                  {new Date(h.occurred_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}
