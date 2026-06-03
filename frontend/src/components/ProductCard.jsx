import { Link } from 'react-router-dom'
import { ShoppingCart, TrendingUp } from 'lucide-react'
import clsx from 'clsx'
import DemandBadge from './DemandBadge'
import { useCart } from '../context/CartContext'

// Deterministic placeholder image using product name initial
const GRADIENTS = [
  'from-violet-600 to-indigo-600',
  'from-blue-600 to-cyan-600',
  'from-emerald-600 to-teal-600',
  'from-orange-600 to-amber-600',
  'from-pink-600 to-rose-600',
  'from-purple-600 to-pink-600',
]

function ProductImage({ product }) {
  const idx = product.name.charCodeAt(0) % GRADIENTS.length
  return (
    <div className={clsx('w-full h-48 rounded-t-xl bg-gradient-to-br flex items-center justify-center', GRADIENTS[idx])}>
      <span className="text-5xl font-black text-white/20 select-none">
        {product.name[0].toUpperCase()}
      </span>
    </div>
  )
}

export default function ProductCard({ product }) {
  const { addToCart } = useCart()

  const isOnSale = parseFloat(product.current_price) < parseFloat(product.base_price)
  const isSurge  = parseFloat(product.current_price) > parseFloat(product.base_price)

  return (
    <div className="group bg-surface-800 rounded-xl border border-surface-700 hover:border-brand-600/50 transition-all duration-200 hover:shadow-lg hover:shadow-brand-600/5 flex flex-col overflow-hidden">

      <Link to={`/products/${product.id}`}>
        <ProductImage product={product} />
      </Link>

      <div className="p-4 flex flex-col gap-3 flex-1">

        {/* Name + SKU */}
        <div>
          <Link to={`/products/${product.id}`}
            className="font-semibold text-sm leading-snug hover:text-brand-500 transition-colors line-clamp-2">
            {product.name}
          </Link>
          <p className="text-xs text-slate-500 mt-0.5">{product.sku}</p>
        </div>

        {/* Price */}
        <div className="flex items-baseline gap-2">
          <span className={clsx(
            'text-xl font-bold tabular-nums transition-colors',
            isSurge && 'text-red-400',
            isOnSale && 'text-emerald-400',
          )}>
            ₹{parseFloat(product.current_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </span>
          {(isOnSale || isSurge) && (
            <span className="text-xs text-slate-500 line-through tabular-nums">
              ₹{parseFloat(product.base_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </span>
          )}
          {isSurge && <TrendingUp className="w-3.5 h-3.5 text-red-400" />}
        </div>

        {/* Stock */}
        <p className={clsx('text-xs', product.stock_quantity > 0 ? 'text-slate-400' : 'text-red-400')}>
          {product.stock_quantity > 0 ? `${product.stock_quantity} in stock` : 'Out of stock'}
        </p>

        {/* Add to cart */}
        <button
          onClick={() => addToCart(product.id)}
          disabled={product.stock_quantity === 0}
          className="mt-auto flex items-center justify-center gap-2 w-full py-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:opacity-40 disabled:cursor-not-allowed text-sm font-medium transition-colors">
          <ShoppingCart className="w-4 h-4" />
          Add to Cart
        </button>

      </div>
    </div>
  )
}
