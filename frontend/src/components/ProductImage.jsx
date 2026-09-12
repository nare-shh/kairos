import { useState } from 'react'
import clsx from 'clsx'

// Deterministic warm placeholder tint, picked from the product name's initial
const TINTS = [
  'bg-clay-100',
  'bg-sage-100',
  'bg-paper-200',
  'bg-clay-300/70',
  'bg-sage-300/60',
  'bg-paper-300',
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

  const idx = (product.name?.charCodeAt(0) || 0) % TINTS.length
  return (
    <div className={clsx('flex items-center justify-center', TINTS[idx], className)}>
      <span className={clsx('display text-ink/20 select-none', textClass)}>
        {product.name?.[0]?.toUpperCase()}
      </span>
    </div>
  )
}
