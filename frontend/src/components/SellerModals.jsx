import { useEffect, useState } from 'react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { categoriesAPI, errorMessage, productsAPI } from '../api/client'
import Modal from './Modal'
import DemandBadge from './DemandBadge'
import { FormField, Spinner, inputClass } from './ui'
import { formatDateTime, inr } from '../lib/format'

// "color: Black" lines <-> {color: "Black"}
const attributesToText = (obj) => Object.entries(obj || {}).map(([k, v]) => `${k}: ${v}`).join('\n')
const textToAttributes = (text) => Object.fromEntries(
  text.split('\n')
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => {
      const i = line.indexOf(':')
      return i === -1 ? [line, ''] : [line.slice(0, i).trim(), line.slice(i + 1).trim()]
    })
    .filter(([key]) => key)
)

function Actions({ onClose, saving, label }) {
  return (
    <div className="flex justify-end gap-3 pt-3">
      <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
      <button type="submit" disabled={saving} className="btn-primary">
        {saving ? <Spinner /> : label}
      </button>
    </div>
  )
}

// ── Create / edit product ─────────────────────────────────────────────────────
export function ProductFormModal({ product, categories, onClose, onSaved }) {
  const editing = Boolean(product)
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({
    name: product?.name ?? '',
    sku: product?.sku ?? '',
    description: product?.description ?? '',
    category_id: product?.category_id ?? '',
    base_price: product?.base_price ?? '',
    min_price: product?.min_price ?? '',
    max_price: product?.max_price ?? '',
    stock_quantity: product?.stock_quantity ?? 10,
    low_stock_threshold: product?.low_stock_threshold ?? 10,
    images: (product?.images ?? []).join('\n'),
    attributes: attributesToText(product?.attributes),
  }))

  const set = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  // New products: suggest a -20% / +30% band around the base price
  const suggestBounds = () => {
    if (editing) return
    const base = Number(form.base_price)
    if (!base) return
    setForm(f => ({
      ...f,
      min_price: f.min_price || (base * 0.8).toFixed(2),
      max_price: f.max_price || (base * 1.3).toFixed(2),
    }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const common = {
      name: form.name.trim(),
      description: form.description.trim(),
      category_id: form.category_id || null,
      min_price: form.min_price,
      max_price: form.max_price,
      low_stock_threshold: Number(form.low_stock_threshold),
      images: form.images.split('\n').map(s => s.trim()).filter(Boolean),
      attributes: textToAttributes(form.attributes),
    }
    try {
      const { data } = editing
        ? await productsAPI.update(product.id, common)
        : await productsAPI.create({
            ...common,
            sku: form.sku.trim(),
            base_price: form.base_price,
            stock_quantity: Number(form.stock_quantity),
          })
      toast.success(editing ? 'Product updated' : 'Listed — Kairos is now pricing it')
      onSaved(data)
    } catch (err) {
      toast.error(errorMessage(err, 'Could not save product'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={editing ? `Edit ${product.name}` : 'List a new product'} onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FormField label="Name">
            <input name="name" value={form.name} onChange={set} required minLength={2} className={inputClass} />
          </FormField>
          <FormField label="SKU" hint={editing ? 'SKUs cannot be changed' : 'Letters, digits and hyphens'}>
            <input name="sku" value={form.sku} onChange={set} required disabled={editing}
              placeholder="AUR-EB-01" className={clsx(inputClass, 'font-mono uppercase')} />
          </FormField>
        </div>

        <FormField label="Description">
          <textarea name="description" value={form.description} onChange={set} rows={3} className={inputClass} />
        </FormField>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <FormField label="Base price" hint={editing ? 'Change it from the price action (audited)' : 'Kairos anchors on this'}>
            <input name="base_price" type="number" step="0.01" min="0.01" value={form.base_price}
              onChange={set} onBlur={suggestBounds} required disabled={editing} className={inputClass} />
          </FormField>
          <FormField label="Floor" hint="Never priced below">
            <input name="min_price" type="number" step="0.01" min="0.01" value={form.min_price} onChange={set} required className={inputClass} />
          </FormField>
          <FormField label="Ceiling" hint="Never priced above">
            <input name="max_price" type="number" step="0.01" min="0.01" value={form.max_price} onChange={set} required className={inputClass} />
          </FormField>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <FormField label="Category">
            <select name="category_id" value={form.category_id} onChange={set} className={inputClass}>
              <option value="">Uncategorised</option>
              {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </FormField>
          <FormField label="Initial stock" hint={editing ? 'Change it from the stock action (audited)' : undefined}>
            <input name="stock_quantity" type="number" min="0" value={form.stock_quantity} onChange={set}
              required disabled={editing} className={inputClass} />
          </FormField>
          <FormField label="Low-stock threshold" hint="Scarcity pricing starts below this">
            <input name="low_stock_threshold" type="number" min="1" value={form.low_stock_threshold} onChange={set} required className={inputClass} />
          </FormField>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FormField label="Attributes" hint="One per line, e.g. color: Midnight Black">
            <textarea name="attributes" value={form.attributes} onChange={set} rows={4}
              placeholder={'color: Midnight Black\nbattery: 30h'} className={clsx(inputClass, 'font-mono text-xs')} />
          </FormField>
          <FormField label="Image URLs" hint="One https:// URL per line (optional)">
            <textarea name="images" value={form.images} onChange={set} rows={4}
              placeholder="https://example.com/photo.jpg" className={clsx(inputClass, 'font-mono text-xs')} />
          </FormField>
        </div>

        <Actions onClose={onClose} saving={saving} label={editing ? 'Save changes' : 'List product'} />
      </form>
    </Modal>
  )
}

// ── Change base price ─────────────────────────────────────────────────────────
export function PriceModal({ product, onClose, onSaved }) {
  const [price, setPrice] = useState(product.base_price)
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await productsAPI.changePrice(product.id, { new_base_price: price, reason: reason.trim() })
      toast.success('Base price updated — Kairos re-anchors within a minute')
      onSaved(data)
    } catch (err) {
      toast.error(errorMessage(err, 'Could not change price'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Base price · ${product.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-5">
        <dl className="divide-y divide-line border-y border-line">
          <div className="flex justify-between py-3 text-sm">
            <dt className="eyebrow">Current base</dt><dd className="tabular-nums">{inr(product.base_price)}</dd>
          </div>
          <div className="flex justify-between py-3 text-sm">
            <dt className="eyebrow">Live price</dt><dd className="tabular-nums">{inr(product.current_price)}</dd>
          </div>
          <div className="flex justify-between py-3 text-sm">
            <dt className="eyebrow">Allowed range</dt>
            <dd className="tabular-nums">{inr(product.min_price)} – {inr(product.max_price)}</dd>
          </div>
        </dl>
        <FormField label="New base price">
          <input type="number" step="0.01" min={product.min_price} max={product.max_price}
            value={price} onChange={e => setPrice(e.target.value)} required className={inputClass} />
        </FormField>
        <FormField label="Reason" hint="Stored permanently in the event log">
          <input value={reason} onChange={e => setReason(e.target.value)} required minLength={5}
            placeholder="Supplier cost increase" className={inputClass} />
        </FormField>
        <Actions onClose={onClose} saving={saving} label="Update price" />
      </form>
    </Modal>
  )
}

// ── Adjust stock ──────────────────────────────────────────────────────────────
export function StockModal({ product, onClose, onSaved }) {
  const [delta, setDelta] = useState(10)
  const [reason, setReason] = useState('Restock')
  const [saving, setSaving] = useState(false)
  const next = product.stock_quantity + Number(delta || 0)

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await productsAPI.adjustStock(product.id, { quantity_delta: Number(delta), reason: reason.trim() })
      toast.success(`Stock is now ${data.stock_quantity}`)
      onSaved(data)
    } catch (err) {
      toast.error(errorMessage(err, 'Could not adjust stock'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Stock · ${product.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-5">
        <div className="flex items-center gap-2 flex-wrap">
          {[-5, -1, 1, 10, 50].map(n => (
            <button key={n} type="button" onClick={() => setDelta(n)}
              className={clsx('px-3.5 py-1.5 rounded-full border text-xs transition-colors',
                Number(delta) === n ? 'bg-sage-900 border-sage-900 text-paper-50' : 'border-line text-ink-500 hover:text-ink')}>
              {n > 0 ? `+${n}` : n}
            </button>
          ))}
        </div>
        <FormField label="Change (negative removes)"
          hint={`${product.stock_quantity} → ${next} units${next <= product.low_stock_threshold ? ' (low stock)' : ''}`}>
          <input type="number" value={delta} onChange={e => setDelta(e.target.value)} required className={inputClass} />
        </FormField>
        <FormField label="Reason">
          <input value={reason} onChange={e => setReason(e.target.value)} required minLength={3} className={inputClass} />
        </FormField>
        <Actions onClose={onClose} saving={saving} label="Apply" />
      </form>
    </Modal>
  )
}

// ── Event history (the audit trail) ───────────────────────────────────────────
function actorLabel(causedBy, sellerId) {
  if (causedBy === 'kairos_pricing_engine') return 'Kairos engine'
  if (causedBy === 'stripe_webhook') return 'Stripe'
  if (causedBy === sellerId) return 'Seller'
  return causedBy ? 'User' : 'System'
}

function describe(event) {
  const p = event.payload || {}
  switch (event.event_type) {
    case 'ProductCreated':
      return `Listed at ${inr(p.base_price)} (range ${inr(p.min_price)}–${inr(p.max_price)}), ${p.stock_quantity} in stock`
    case 'ProductPriceChanged':
      return 'new_base_price' in p
        ? `Base price ${inr(p.old_base_price)} to ${inr(p.new_base_price)} — ${p.reason}`
        : `Live price ${inr(p.old_price)} to ${inr(p.new_price)} (score ${p.demand_score}, ${p.triggering_event})`
    case 'ProductStockUpdated':
      return `Stock ${p.old_quantity} to ${p.new_quantity} (${p.delta > 0 ? '+' : ''}${p.delta}) — ${p.reason}`
    case 'ProductUpdated':
      return `Changed ${Object.keys(p.changes || {}).join(', ')}`
    case 'ProductActivated':   return 'Shown in the store'
    case 'ProductDeactivated': return 'Hidden from the store'
    case 'ProductDeleted':     return 'Deleted'
    default:                   return ''
  }
}

export function EventsModal({ product, onClose }) {
  const [events, setEvents] = useState(null)

  useEffect(() => {
    productsAPI.events(product.id)
      .then(r => setEvents([...r.data].reverse()))
      .catch(err => { toast.error(errorMessage(err, 'Could not load history')); setEvents([]) })
  }, [product.id])

  return (
    <Modal title={`History · ${product.name}`} onClose={onClose} wide>
      {!events ? (
        <div className="flex justify-center py-10"><Spinner className="w-6 h-6" tone="dark" /></div>
      ) : events.length === 0 ? (
        <p className="text-sm text-ink-500">No events.</p>
      ) : (
        <>
          <p className="eyebrow mb-4">Append-only event log, newest first</p>
          <div className="max-h-[60vh] overflow-y-auto divide-y divide-line border-t border-line">
            {events.map(e => (
              <details key={e.id} className="group py-4">
                <summary className="flex flex-wrap items-center gap-x-4 gap-y-2 cursor-pointer list-none text-sm">
                  <span className="eyebrow w-8 flex-shrink-0">{String(e.version).padStart(2, '0')}</span>
                  <span className="text-ink">{e.event_type}</span>
                  {e.payload?.demand_level && <DemandBadge level={e.payload.demand_level} />}
                  <span className="text-xs text-ink-500">{actorLabel(e.caused_by, product.seller_id)}</span>
                  <span className="text-xs text-ink-400 ml-auto whitespace-nowrap">{formatDateTime(e.occurred_at)}</span>
                  <span className="basis-full text-xs text-ink-500">{describe(e)}</span>
                </summary>
                <pre className="mt-3 p-3 rounded-xl bg-paper-200 text-[11px] text-ink-700 overflow-x-auto">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        </>
      )}
    </Modal>
  )
}

// ── Create category (admin) ───────────────────────────────────────────────────
export function CategoryModal({ categories, onClose, onSaved }) {
  const [form, setForm] = useState({ name: '', parent_id: '', description: '' })
  const [saving, setSaving] = useState(false)
  const set = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const { data } = await categoriesAPI.create({
        name: form.name.trim(),
        description: form.description.trim() || null,
        parent_id: form.parent_id || null,
      })
      toast.success(`Category ${data.name} created`)
      onSaved(data)
    } catch (err) {
      toast.error(errorMessage(err, 'Could not create category'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="New category" onClose={onClose}>
      <form onSubmit={submit} className="space-y-5">
        <FormField label="Name">
          <input name="name" value={form.name} onChange={set} required minLength={2} className={inputClass} />
        </FormField>
        <FormField label="Parent category">
          <select name="parent_id" value={form.parent_id} onChange={set} className={inputClass}>
            <option value="">None (top level)</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </FormField>
        <FormField label="Description">
          <input name="description" value={form.description} onChange={set} className={inputClass} />
        </FormField>
        <Actions onClose={onClose} saving={saving} label="Create" />
      </form>
    </Modal>
  )
}
