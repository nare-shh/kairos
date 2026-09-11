// Indian Rupee with two decimals: 1234.5 → "₹1,234.50"
export const inr = (value) =>
  `₹${Number(value ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export const percentChange = (current, base) => {
  const c = Number(current)
  const b = Number(base)
  if (!b) return 0
  return ((c - b) / b) * 100
}

export const formatDateTime = (iso) =>
  new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
