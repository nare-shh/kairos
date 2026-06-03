import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { BarChart2, TrendingUp, Package, Zap, Eye } from 'lucide-react'
import { productsAPI, intentAPI } from '../api/client'
import { useAuth } from '../context/AuthContext'
import DemandBadge from '../components/DemandBadge'

function ScoreCard({ product }) {
  const [score, setScore] = useState(null)

  useEffect(() => {
    intentAPI.score(product.id).then(r => setScore(r.data)).catch(() => {})
    const interval = setInterval(() => {
      intentAPI.score(product.id).then(r => setScore(r.data)).catch(() => {})
    }, 10000) // refresh every 10s
    return () => clearInterval(interval)
  }, [product.id])

  const priceChange = score
    ? ((parseFloat(product.current_price) - parseFloat(product.base_price)) / parseFloat(product.base_price) * 100).toFixed(1)
    : 0

  return (
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 hover:border-brand-600/30 transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div>
          <Link to={`/products/${product.id}`} className="font-semibold text-sm hover:text-brand-500 transition-colors">
            {product.name}
          </Link>
          <p className="text-xs text-slate-500 mt-0.5">{product.sku}</p>
        </div>
        {score && <DemandBadge level={score.demand_level} />}
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-surface-700 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Current Price</p>
          <p className="text-lg font-bold tabular-nums">
            ₹{parseFloat(product.current_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </p>
          {parseFloat(priceChange) !== 0 && (
            <p className={`text-xs flex items-center gap-0.5 mt-0.5 ${parseFloat(priceChange) > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
              <TrendingUp className="w-3 h-3" />
              {parseFloat(priceChange) > 0 ? '+' : ''}{priceChange}% vs base
            </p>
          )}
        </div>
        <div className="bg-surface-700 rounded-lg p-3">
          <p className="text-xs text-slate-500 mb-1">Demand Score</p>
          <p className="text-lg font-bold tabular-nums">{score?.demand_score?.toFixed(1) ?? '—'}</p>
          {score?.cart_adds_1h > 0 && (
            <p className="text-xs text-slate-400 mt-0.5">{score.cart_adds_1h} cart adds / 1h</p>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="flex items-center gap-1">
          <Eye className="w-3 h-3" />
          {score?.active_viewers ?? 0} active viewers
        </span>
        <span className="flex items-center gap-1">
          <Package className="w-3 h-3" />
          {product.stock_quantity} in stock
        </span>
        <span className="text-brand-500/70 flex items-center gap-1">
          <Zap className="w-3 h-3" />
          {score?.price_multiplier ? `×${score.price_multiplier.toFixed(2)}` : '×1.00'}
        </span>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [products, setProducts] = useState([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    if (!user) return
    productsAPI.list({ seller_id: user.id, page_size: 20 })
      .then(r => setProducts(r.data.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [user])

  if (!user || (user.role !== 'seller' && user.role !== 'admin')) {
    return <div className="text-center py-24 text-slate-500">Seller access only.</div>
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <BarChart2 className="w-6 h-6 text-brand-500" /> Seller Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Live demand scores refresh every 10 seconds.
            <span className="inline-flex items-center gap-1 ml-2">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              <span className="text-emerald-500">Live</span>
            </span>
          </p>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => <div key={i} className="h-52 bg-surface-700 rounded-xl animate-pulse" />)}
        </div>
      ) : products.length === 0 ? (
        <div className="text-center py-24 text-slate-500">
          <Package className="w-10 h-10 mx-auto mb-3 opacity-40" />
          <p>No products yet.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {products.map(p => <ScoreCard key={p.id} product={p} />)}
        </div>
      )}
    </div>
  )
}
