import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  TrendingUp, TrendingDown, Package, Zap, Eye, EyeOff, Plus, Pencil, Tag, Boxes,
  History, Trash2, FolderPlus, Flame, AlertTriangle,
} from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { categoriesAPI, errorMessage, intentAPI, productsAPI, tokens, WS_BASE } from '../api/client'
import { useAuth } from '../context/AuthContext'
import DemandBadge from '../components/DemandBadge'
import ProductImage from '../components/ProductImage'
import { CategoryModal, EventsModal, PriceModal, ProductFormModal, StockModal } from '../components/SellerModals'
import { inr, percentChange } from '../lib/format'

const SCORE_REFRESH_MS = 10000

function Stat({ label, value, accent }) {
  return (
    <div className="py-6 px-5 sm:px-8 first:pl-0">
      <p className={clsx('display text-3xl leading-none tabular-nums', accent)}>{value}</p>
      <p className="eyebrow mt-2">{label}</p>
    </div>
  )
}

function IconButton({ icon: Icon, label, onClick, danger }) {
  return (
    <button onClick={onClick} title={label} aria-label={label}
      className={clsx('p-2 rounded-full transition-colors',
        danger ? 'text-ink-400 hover:text-flag-up hover:bg-paper-200' : 'text-ink-500 hover:text-ink hover:bg-paper-200')}>
      <Icon className="w-4 h-4" />
    </button>
  )
}

function ProductManageCard({ product, score, flashing, onAction }) {
  const change = percentChange(product.current_price, product.base_price)
  const lowStock = product.stock_quantity <= product.low_stock_threshold

  return (
    <article className={clsx('flex flex-col rounded-2xl border bg-paper-50 p-5 transition-colors',
      product.is_active ? 'border-line hover:border-line-strong' : 'border-dashed border-line-strong')}>
      <div className="flex items-start gap-4 pb-4 border-b border-line">
        <ProductImage product={product} className="w-12 h-12 rounded-xl flex-shrink-0" textClass="text-xl" />
        <div className="min-w-0 flex-1">
          <p className="eyebrow mb-1">{product.sku}</p>
          {product.is_active ? (
            <Link to={`/products/${product.id}`} className="display text-lg leading-snug line-clamp-1 hover:text-sage-700 transition-colors">
              {product.name}
            </Link>
          ) : (
            <p className="display text-lg leading-snug line-clamp-1 text-ink-500">{product.name}</p>
          )}
        </div>
        {product.is_active
          ? score && <DemandBadge level={score.demand_level} />
          : <span className="px-2.5 py-1 rounded-full border border-line text-[11px] uppercase tracking-caps text-ink-500">Hidden</span>}
      </div>

      <dl className="grid grid-cols-2 gap-4 py-5">
        <div>
          <dt className="eyebrow mb-1.5">Live price</dt>
          <dd className={clsx('display text-2xl tabular-nums transition-colors', flashing && 'text-sage-600')}>
            {inr(product.current_price)}
          </dd>
          <dd className={clsx('text-xs flex items-center gap-1 mt-1',
            change > 0 ? 'text-flag-up' : change < 0 ? 'text-sage-700' : 'text-ink-400')}>
            {change > 0 ? <TrendingUp className="w-3 h-3" /> : change < 0 ? <TrendingDown className="w-3 h-3" /> : null}
            {change === 0 ? 'at base' : `${change > 0 ? '+' : ''}${change.toFixed(1)}% vs ${inr(product.base_price)}`}
          </dd>
        </div>
        <div>
          <dt className="eyebrow mb-1.5">Demand score</dt>
          <dd className="display text-2xl tabular-nums">{score?.demand_score?.toFixed(1) ?? '—'}</dd>
          <dd className="text-xs text-ink-500 mt-1">{score?.cart_adds_1h ?? 0} cart adds / 1h</dd>
        </div>
      </dl>

      <div className="flex items-center justify-between gap-3 text-xs text-ink-500 pb-4 border-b border-line">
        <span className="flex items-center gap-1.5"><Eye className="w-3 h-3" />{score?.active_viewers ?? 0} viewers</span>
        <span className={clsx('flex items-center gap-1.5', lowStock && 'text-flag-warn')}>
          {lowStock ? <AlertTriangle className="w-3 h-3" /> : <Package className="w-3 h-3" />}
          {product.stock_quantity} in stock
        </span>
        <span className="flex items-center gap-1.5 text-sage-700">
          <Zap className="w-3 h-3" />
          {score?.price_multiplier ? `×${score.price_multiplier.toFixed(2)}` : '×1.00'}
        </span>
      </div>

      <p className="text-[11px] text-ink-400 py-3">
        Kairos range {inr(product.min_price)} – {inr(product.max_price)}
      </p>

      <div className="flex items-center gap-1 mt-auto pt-1">
        <IconButton icon={Pencil}  label="Edit details"      onClick={() => onAction('edit', product)} />
        <IconButton icon={Tag}     label="Change base price" onClick={() => onAction('price', product)} />
        <IconButton icon={Boxes}   label="Adjust stock"      onClick={() => onAction('stock', product)} />
        <IconButton icon={History} label="Event history"     onClick={() => onAction('events', product)} />
        <IconButton icon={product.is_active ? EyeOff : Eye} label={product.is_active ? 'Hide from store' : 'Show in store'}
          onClick={() => onAction('toggle', product)} />
        <span className="flex-1" />
        <IconButton icon={Trash2} label="Delete" danger onClick={() => onAction('delete', product)} />
      </div>
    </article>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'

  const [products,   setProducts]   = useState([])
  const [scores,     setScores]     = useState({})
  const [categories, setCategories] = useState([])
  const [loading,    setLoading]    = useState(true)
  const [modal,      setModal]      = useState(null)     // { type, product }
  const [live,       setLive]       = useState(false)
  const [flashing,   setFlashing]   = useState(null)

  const productsRef = useRef(products)
  productsRef.current = products

  const loadProducts = useCallback(async () => {
    try {
      const { data } = await productsAPI.mine({ page_size: 100 })
      setProducts(data.items)
    } catch (e) {
      toast.error(errorMessage(e, 'Could not load your products'))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadScores = useCallback(async () => {
    const active = productsRef.current.filter(p => p.is_active)
    const results = await Promise.allSettled(active.map(p => intentAPI.score(p.id)))
    setScores(prev => {
      const next = { ...prev }
      results.forEach(r => { if (r.status === 'fulfilled') next[r.value.data.product_id] = r.value.data })
      return next
    })
  }, [])

  useEffect(() => {
    loadProducts()
    categoriesAPI.list().then(r => setCategories(r.data)).catch(() => {})
  }, [loadProducts])

  // Demand scores: refresh every 10 seconds
  useEffect(() => {
    if (!products.length) return
    loadScores()
    const timer = setInterval(loadScores, SCORE_REFRESH_MS)
    return () => clearInterval(timer)
  }, [products.length, loadScores])

  // Live price feed for the whole catalog (reconnects when products change)
  useEffect(() => {
    if (!products.length) return
    let ws
    let retryTimer
    let flashTimer
    let closedByUs = false

    const connect = () => {
      const token = tokens.access()   // read fresh — it may have been refreshed
      if (!token) return
      ws = new WebSocket(`${WS_BASE}/ws/dashboard?token=${encodeURIComponent(token)}`)
      ws.onopen = () => setLive(true)
      ws.onmessage = (e) => {
        let msg
        try { msg = JSON.parse(e.data) } catch { return }
        if (msg.type !== 'price_update') return
        setProducts(list => list.map(p => (p.id === msg.product_id ? { ...p, current_price: msg.new_price } : p)))
        setScores(s => (s[msg.product_id]
          ? { ...s, [msg.product_id]: { ...s[msg.product_id], demand_level: msg.demand_level, demand_score: msg.demand_score } }
          : s))
        setFlashing(msg.product_id)
        clearTimeout(flashTimer)
        flashTimer = setTimeout(() => setFlashing(null), 1000)
      }
      ws.onclose = () => {
        setLive(false)
        if (!closedByUs) retryTimer = setTimeout(connect, 5000)
      }
    }

    connect()
    return () => {
      closedByUs = true
      clearTimeout(retryTimer)
      clearTimeout(flashTimer)
      ws?.close()
    }
  }, [products.length])

  const upsert = (product) => setProducts(list =>
    list.some(p => p.id === product.id)
      ? list.map(p => (p.id === product.id ? product : p))
      : [product, ...list]
  )

  const handleAction = async (type, product) => {
    if (type === 'toggle') {
      try {
        const { data } = await (product.is_active ? productsAPI.deactivate(product.id) : productsAPI.activate(product.id))
        upsert(data)
        toast.success(data.is_active ? 'Product is live in the store' : 'Product hidden from the store')
      } catch (e) {
        toast.error(errorMessage(e))
      }
      return
    }
    if (type === 'delete') {
      if (!window.confirm(`Delete "${product.name}"? It is removed from the store; order and event history is kept.`)) return
      try {
        await productsAPI.remove(product.id)
        setProducts(list => list.filter(p => p.id !== product.id))
        toast.success('Product deleted')
      } catch (e) {
        toast.error(errorMessage(e))
      }
      return
    }
    setModal({ type, product })
  }

  const closeModal = () => setModal(null)
  const savedProduct = (product) => { upsert(product); closeModal() }

  const activeCount = products.filter(p => p.is_active).length
  const unitCount = products.reduce((sum, p) => sum + p.stock_quantity, 0)
  const hotCount = Object.values(scores).filter(s => s.demand_level === 'high' || s.demand_level === 'surge').length

  return (
    <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12">
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="eyebrow mb-4 flex items-center gap-2">
            {isAdmin ? 'Every product' : 'Your catalog'}
            <span className="inline-flex items-center gap-1.5">
              <span className={clsx('w-1.5 h-1.5 rounded-full', live ? 'bg-sage-500 animate-pulse' : 'bg-ink-400')} />
              {live ? 'Live' : 'Offline'}
            </span>
          </p>
          <h1 className="display text-5xl">Seller desk.</h1>
        </div>
        <div className="flex gap-3">
          {isAdmin && (
            <button onClick={() => setModal({ type: 'category' })} className="btn-ghost">
              <FolderPlus className="w-4 h-4" /> New category
            </button>
          )}
          <button onClick={() => setModal({ type: 'create' })} className="btn-primary">
            <Plus className="w-4 h-4" /> New product
          </button>
        </div>
      </div>

      <dl className="grid grid-cols-2 lg:grid-cols-4 divide-x divide-line border-y border-line my-10">
        <Stat label="Products" value={products.length} />
        <Stat label="Live in store" value={activeCount} />
        <Stat label="Units in stock" value={unitCount} />
        <Stat label="High demand now" value={hotCount} accent={hotCount ? 'text-flag-warn' : undefined} />
      </dl>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[...Array(6)].map((_, i) => <div key={i} className="h-80 rounded-2xl border border-line bg-paper-50 animate-pulse" />)}
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-24">
          <p className="display text-3xl mb-3">No products yet.</p>
          <p className="text-ink-500 mb-8">List your first one and Kairos starts pricing it.</p>
          <button onClick={() => setModal({ type: 'create' })} className="btn-primary">
            <Plus className="w-4 h-4" /> New product
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {products.map(p => (
            <ProductManageCard key={p.id} product={p} score={scores[p.id]}
              flashing={flashing === p.id} onAction={handleAction} />
          ))}
        </div>
      )}

      {modal?.type === 'create' && (
        <ProductFormModal categories={categories} onClose={closeModal} onSaved={savedProduct} />
      )}
      {modal?.type === 'edit' && (
        <ProductFormModal product={modal.product} categories={categories} onClose={closeModal} onSaved={savedProduct} />
      )}
      {modal?.type === 'price' && <PriceModal product={modal.product} onClose={closeModal} onSaved={savedProduct} />}
      {modal?.type === 'stock' && <StockModal product={modal.product} onClose={closeModal} onSaved={savedProduct} />}
      {modal?.type === 'events' && <EventsModal product={modal.product} onClose={closeModal} />}
      {modal?.type === 'category' && (
        <CategoryModal categories={categories} onClose={closeModal}
          onSaved={(c) => { setCategories(list => [...list, c].sort((a, b) => a.name.localeCompare(b.name))); closeModal() }} />
      )}
    </div>
  )
}
