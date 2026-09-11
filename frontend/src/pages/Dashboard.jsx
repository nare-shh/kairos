import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart2, TrendingUp, TrendingDown, Package, Zap, Eye, EyeOff, Plus, Pencil, Tag, Boxes,
  History, Trash2, FolderPlus, Flame, AlertTriangle,
} from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { categoriesAPI, errorMessage, intentAPI, productsAPI, tokens, WS_BASE } from '../api/client'
import { useAuth } from '../context/AuthContext'
import DemandBadge from '../components/DemandBadge'
import ProductImage from '../components/ProductImage'
import { CategoryModal, EventsModal, PriceModal, ProductFormModal, StockModal } from '../components/SellerModals'
import { primaryButton, secondaryButton } from '../components/ui'
import { inr, percentChange } from '../lib/format'

const SCORE_REFRESH_MS = 10000

function Stat({ icon: Icon, label, value, accent }) {
  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-4">
      <p className="text-xs text-slate-500 flex items-center gap-1.5 mb-1"><Icon className="w-3.5 h-3.5" /> {label}</p>
      <p className={clsx('text-2xl font-bold tabular-nums', accent)}>{value}</p>
    </div>
  )
}

function IconButton({ icon: Icon, label, onClick, danger }) {
  return (
    <button onClick={onClick} title={label} aria-label={label}
      className={clsx('p-2 rounded-lg transition-colors',
        danger ? 'text-slate-500 hover:text-red-400 hover:bg-red-400/10' : 'text-slate-400 hover:text-white hover:bg-surface-600')}>
      <Icon className="w-4 h-4" />
    </button>
  )
}

function ProductManageCard({ product, score, flashing, onAction }) {
  const change = percentChange(product.current_price, product.base_price)
  const lowStock = product.stock_quantity <= product.low_stock_threshold

  return (
    <div className={clsx(
      'bg-surface-800 border rounded-xl p-5 transition-colors flex flex-col',
      product.is_active ? 'border-surface-700 hover:border-brand-600/30' : 'border-dashed border-surface-600 opacity-70',
    )}>
      <div className="flex items-start gap-3 mb-4">
        <ProductImage product={product} className="w-11 h-11 rounded-lg flex-shrink-0" textClass="text-lg" />
        <div className="min-w-0 flex-1">
          {product.is_active ? (
            <Link to={`/products/${product.id}`} className="font-semibold text-sm hover:text-brand-500 transition-colors line-clamp-1">
              {product.name}
            </Link>
          ) : (
            <p className="font-semibold text-sm line-clamp-1">{product.name}</p>
          )}
          <p className="text-xs text-slate-500 mt-0.5 font-mono">{product.sku}</p>
        </div>
        {product.is_active
          ? score && <DemandBadge level={score.demand_level} />
          : <span className="px-2 py-0.5 rounded-full text-[11px] bg-slate-500/10 text-slate-400 border border-slate-500/20">Hidden</span>}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-surface-700 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Live Price</p>
          <p className={clsx('text-lg font-bold tabular-nums transition-colors', flashing && 'text-emerald-400')}>
            {inr(product.current_price)}
          </p>
          <p className={clsx('text-xs flex items-center gap-0.5 mt-0.5',
            change > 0 ? 'text-red-400' : change < 0 ? 'text-emerald-400' : 'text-slate-500')}>
            {change > 0 ? <TrendingUp className="w-3 h-3" /> : change < 0 ? <TrendingDown className="w-3 h-3" /> : null}
            {change === 0 ? 'at base' : `${change > 0 ? '+' : ''}${change.toFixed(1)}% vs ${inr(product.base_price)}`}
          </p>
        </div>
        <div className="bg-surface-700 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Demand Score</p>
          <p className="text-lg font-bold tabular-nums">{score?.demand_score?.toFixed(1) ?? '—'}</p>
          <p className="text-xs text-slate-400 mt-0.5">{score?.cart_adds_1h ?? 0} cart adds / 1h</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500 mb-4">
        <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{score?.active_viewers ?? 0} viewers</span>
        <span className={clsx('flex items-center gap-1', lowStock && 'text-amber-400')}>
          {lowStock ? <AlertTriangle className="w-3 h-3" /> : <Package className="w-3 h-3" />}
          {product.stock_quantity} in stock
        </span>
        <span className="text-brand-500/70 flex items-center gap-1">
          <Zap className="w-3 h-3" />
          {score?.price_multiplier ? `×${score.price_multiplier.toFixed(2)}` : '×1.00'}
        </span>
      </div>

      <p className="text-[11px] text-slate-600 mb-3">
        Kairos range {inr(product.min_price)} – {inr(product.max_price)}
      </p>

      <div className="flex items-center gap-1 border-t border-surface-700 pt-3 mt-auto">
        <IconButton icon={Pencil}  label="Edit details"      onClick={() => onAction('edit', product)} />
        <IconButton icon={Tag}     label="Change base price" onClick={() => onAction('price', product)} />
        <IconButton icon={Boxes}   label="Adjust stock"      onClick={() => onAction('stock', product)} />
        <IconButton icon={History} label="Event history"     onClick={() => onAction('events', product)} />
        <IconButton icon={product.is_active ? EyeOff : Eye} label={product.is_active ? 'Hide from store' : 'Show in store'}
          onClick={() => onAction('toggle', product)} />
        <span className="flex-1" />
        <IconButton icon={Trash2} label="Delete" danger onClick={() => onAction('delete', product)} />
      </div>
    </div>
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

  // Live price feed for the whole catalog (reconnects when products are added/removed)
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
      if (!window.confirm(`Delete “${product.name}”? It is removed from the store; its order and event history is kept.`)) return
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
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-brand-500" /> {isAdmin ? 'Catalog Dashboard' : 'Seller Dashboard'}
          </h1>
          <p className="text-sm text-slate-500 mt-1 flex flex-wrap items-center gap-x-2">
            Demand scores refresh every 10 seconds; prices update live.
            <span className="inline-flex items-center gap-1">
              <span className={clsx('w-1.5 h-1.5 rounded-full', live ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600')} />
              <span className={live ? 'text-emerald-500' : 'text-slate-500'}>{live ? 'Live' : 'Offline'}</span>
            </span>
          </p>
        </div>
        <div className="flex gap-2">
          {isAdmin && (
            <button onClick={() => setModal({ type: 'category' })} className={secondaryButton}>
              <FolderPlus className="w-4 h-4" /> New category
            </button>
          )}
          <button onClick={() => setModal({ type: 'create' })} className={primaryButton}>
            <Plus className="w-4 h-4" /> New product
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat icon={Package} label="Products" value={products.length} />
        <Stat icon={Eye} label="Live in store" value={activeCount} />
        <Stat icon={Boxes} label="Units in stock" value={unitCount} />
        <Stat icon={Flame} label="High demand now" value={hotCount} accent={hotCount ? 'text-orange-400' : undefined} />
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => <div key={i} className="h-72 bg-surface-700 rounded-xl animate-pulse" />)}
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-24 text-slate-500">
          <Package className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p className="mb-6">No products yet — list your first one and Kairos starts pricing it.</p>
          <button onClick={() => setModal({ type: 'create' })} className={primaryButton}>
            <Plus className="w-4 h-4" /> New product
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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
