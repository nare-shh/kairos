import { Link } from 'react-router-dom'
import { ArrowUpRight, TrendingUp, TrendingDown } from 'lucide-react'
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
  const soldOut  = product.stock_quantity === 0
  const lowStock = !soldOut && product.stock_quantity <= product.low_stock_threshold

  return (
    <article className="group flex flex-col bg-paper-50 border border-line rounded-2xl overflow-hidden transition-colors hover:border-line-strong">
      <Link to={`/products/${product.id}`} className="relative block">
        <ProductImage product={product} className="w-full h-52" textClass="text-6xl" />
        {(lowStock || soldOut) && (
          <span className="absolute top-3 left-3 px-2.5 py-1 rounded-full bg-paper-50/95 border border-line text-[10px] uppercase tracking-caps text-ink-700">
            {soldOut ? 'Sold out' : `Only ${product.stock_quantity} left`}
          </span>
        )}
      </Link>

      <div className="flex flex-col gap-3 p-5 flex-1">
        <div>
          <p className="eyebrow mb-1">{product.sku}</p>
          <Link to={`/products/${product.id}`}
            className="display text-xl leading-snug line-clamp-2 transition-colors hover:text-sage-700">
            {product.name}
          </Link>
        </div>

        <div className="flex items-baseline gap-2 mt-auto">
          <span className={clsx('display text-2xl tabular-nums', isSurge && 'text-flag-up', isOnSale && 'text-sage-700')}>
            {inr(current)}
          </span>
          {(isOnSale || isSurge) && (
            <>
              <span className="text-xs text-ink-400 line-through tabular-nums">{inr(base)}</span>
              {isSurge
                ? <TrendingUp className="w-3.5 h-3.5 text-flag-up" />
                : <TrendingDown className="w-3.5 h-3.5 text-sage-600" />}
            </>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 pt-3 border-t border-line">
          <span className="text-xs text-ink-500">
            {soldOut ? 'Out of stock' : `${product.stock_quantity} in stock`}
          </span>
          <button
            onClick={() => addToCart(product.id)}
            disabled={soldOut}
            className="inline-flex items-center gap-1.5 text-sm font-medium text-ink transition-colors hover:text-sage-700 disabled:opacity-40 disabled:cursor-not-allowed">
            Add to cart
            <ArrowUpRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </button>
        </div>
      </div>
    </article>
  )
}
