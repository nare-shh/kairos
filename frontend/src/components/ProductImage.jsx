import { useState } from 'react'
import clsx from 'clsx'

// Deterministic placeholder using the product name's initial
const GRADIENTS = [
  'from-violet-600 to-indigo-600',
  'from-blue-600 to-cyan-600',
  'from-emerald-600 to-teal-600',
  'from-orange-600 to-amber-600',
  'from-pink-600 to-rose-600',
  'from-purple-600 to-pink-600',
]

export default function ProductImage({ product, className, textClass = 'text-5xl' }) {
  const [broken, setBroken] = useState(false)
  const url = product.images?.[0]

  if (url && !broken) {
    return (
      <img src={url} alt={product.name} loading="lazy" onError={() => setBroken(true)}
        className={clsx('object-cover', className)} />
    )
  }

  const idx = (product.name?.charCodeAt(0) || 0) % GRADIENTS.length
  return (
    <div className={clsx('bg-gradient-to-br flex items-center justify-center', GRADIENTS[idx], className)}>
      <span className={clsx('font-black text-white/20 select-none', textClass)}>
        {product.name?.[0]?.toUpperCase()}
      </span>
    </div>
  )
}
