import { Link } from 'react-router-dom'
import { ShoppingCart, TrendingUp, TrendingDown } from 'lucide-react'
import clsx from 'clsx'
import ProductImage from './ProductImage'
import { useCart } from '../context/CartContext'
import { inr } from '../lib/format'

export default function ProductCard({ product }) {
  const { addToCart } = useCart()

  const current = Number(product.current_price)
  const base = Number(product.base_price)
  const isOnSale = current < base
  const isSurge  = current > base
  const lowStock = product.stock_quantity > 0 && product.stock_quantity <= product.low_stock_threshold

  return (
    <div className="group bg-surface-800 rounded-xl border border-surface-700 hover:border-brand-600/50 transition-all duration-200 hover:shadow-lg hover:shadow-brand-600/5 flex flex-col overflow-hidden">

      <Link to={`/products/${product.id}`} className="relative">
        <ProductImage product={product} className="w-full h-48" />
        {lowStock && (
          <span className="absolute top-2 left-2 px-2 py-0.5 rounded-full bg-amber-500/90 text-[11px] font-semibold text-black">
            Only {product.stock_quantity} left
          </span>
        )}
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
            {inr(current)}
          </span>
          {(isOnSale || isSurge) && (
            <span className="text-xs text-slate-500 line-through tabular-nums">{inr(base)}</span>
          )}
          {isSurge && <TrendingUp className="w-3.5 h-3.5 text-red-400" />}
          {isOnSale && <TrendingDown className="w-3.5 h-3.5 text-emerald-400" />}
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
