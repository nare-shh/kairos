import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, CheckCircle2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { errorMessage, ordersAPI, trackIntent } from '../api/client'
import { useCart } from '../context/CartContext'
import PaymentPanel from '../components/PaymentPanel'
import OrderStatusBadge from '../components/OrderStatusBadge'
import { FormField, PageLoader, Spinner, inputClass } from '../components/ui'
import { inr } from '../lib/format'

const TAX_RATE = 0.18   // must match the backend (order_service.TAX_RATE)

const Field = ({ label, name, value, onChange, placeholder, required }) => (
  <FormField label={label}>
    <input name={name} value={value} onChange={onChange} placeholder={placeholder} required={required} className={inputClass} />
  </FormField>
)

function Summary({ cart }) {
  const subtotal = Number(cart.subtotal)
  const tax = Math.round(subtotal * TAX_RATE * 100) / 100
  return (
    <div className="card p-6 sticky top-24">
      <h2 className="eyebrow mb-5">Order summary</h2>
      <ul className="divide-y divide-line">
        {cart.items.map(i => (
          <li key={i.product_id} className="flex justify-between gap-3 py-3 text-sm">
            <span className="text-ink-700 truncate">{i.quantity} × {i.product_name}</span>
            <span className="tabular-nums flex-shrink-0">{inr(i.total_price)}</span>
          </li>
        ))}
      </ul>
      <dl className="space-y-3 text-sm mt-5 pt-5 border-t border-line">
        <div className="flex justify-between"><dt className="text-ink-500">Subtotal</dt><dd className="tabular-nums">{inr(subtotal)}</dd></div>
        <div className="flex justify-between"><dt className="text-ink-500">Tax (18% GST)</dt><dd className="tabular-nums">{inr(tax)}</dd></div>
        <div className="flex justify-between"><dt className="text-ink-500">Shipping</dt><dd className="text-sage-700">Free</dd></div>
      </dl>
      <div className="flex items-baseline justify-between gap-4 mt-5 pt-5 border-t border-line">
        <span className="eyebrow">Total</span>
        <span className="display text-3xl tabular-nums">{inr(subtotal + tax)}</span>
      </div>
      <p className="text-[11px] text-ink-400 mt-4 leading-relaxed">
        Live Kairos prices, locked in the moment you place the order.
      </p>
    </div>
  )
}

export default function Checkout() {
  const navigate = useNavigate()
  const { cart, fetchCart } = useCart()
  const [step,     setStep]     = useState('address')   // address → payment → done
  const [loading,  setLoading]  = useState(false)
  const [checkout, setCheckout] = useState(null)        // CheckoutResponse
  const [paidOrder, setPaidOrder] = useState(null)

  const [form, setForm] = useState({
    full_name: '', line1: '', line2: '', city: '',
    state: '', postal_code: '', country: 'IN', phone: '',
  })

  // ── Demand signals ────────────────────────────────────────────────────────
  // Starting checkout is strong purchase intent; leaving before placing the
  // order is an abandonment. The mounted ref ignores React StrictMode's
  // simulated unmount in development.
  const startedFor = useRef(null)
  const stepRef = useRef(step)
  const mounted = useRef(false)
  stepRef.current = step

  useEffect(() => { fetchCart() }, [fetchCart])

  useEffect(() => {
    if (!cart || cart.is_empty || startedFor.current) return
    startedFor.current = cart.items.map(i => i.product_id)
    // The signal can move the price itself — re-read the cart so the summary
    // shows exactly what "Place order" will charge
    Promise.all(startedFor.current.map(id => trackIntent(id, 'CheckoutStarted')))
      .then(() => fetchCart())
  }, [cart, fetchCart])

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      setTimeout(() => {
        if (!mounted.current && startedFor.current && stepRef.current === 'address') {
          startedFor.current.forEach(id => trackIntent(id, 'CheckoutAbandoned'))
        }
      }, 0)
    }
  }, [])

  const handleChange = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await ordersAPI.checkout({ shipping_address: form, notes: null })
      setCheckout(data)
      setStep('payment')
      fetchCart()   // the server emptied the cart
    } catch (err) {
      toast.error(errorMessage(err, 'Checkout failed. Check your cart.'))
    } finally {
      setLoading(false)
    }
  }

  const handlePaid = (order) => {
    setPaidOrder(order ?? checkout.order)
    setStep('done')
    toast.success('Payment complete')
  }

  // ── Done ──────────────────────────────────────────────────────────────────
  if (step === 'done') {
    const order = paidOrder
    return (
      <div className="max-w-lg mx-auto px-5 py-24 text-center animate-slide-up">
        <CheckCircle2 className="w-12 h-12 text-sage-600 mx-auto mb-6" />
        <p className="eyebrow mb-4">Order placed</p>
        <h1 className="display text-5xl mb-6">Thank you.</h1>
        <p className="font-mono text-sm text-ink-700 mb-3">{order.order_number}</p>
        <div className="mb-10"><OrderStatusBadge status={order.status} /></div>

        <dl className="card p-6 text-left space-y-3 text-sm mb-8">
          <div className="flex justify-between"><dt className="text-ink-500">Subtotal</dt><dd className="tabular-nums">{inr(order.subtotal)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-500">Tax</dt><dd className="tabular-nums">{inr(order.tax_amount)}</dd></div>
          <div className="flex items-baseline justify-between pt-3 border-t border-line">
            <dt className="eyebrow">Charged</dt>
            <dd className="display text-2xl tabular-nums">{inr(order.total_amount)}</dd>
          </div>
        </dl>

        <div className="flex gap-3 justify-center">
          <button onClick={() => navigate('/orders')} className="btn-ghost">View orders</button>
          <button onClick={() => navigate('/')} className="btn-primary">Keep shopping</button>
        </div>
      </div>
    )
  }

  // ── Payment ───────────────────────────────────────────────────────────────
  if (step === 'payment' && checkout) {
    return (
      <div className="max-w-lg mx-auto px-5 sm:px-8 py-12 animate-slide-up">
        <p className="eyebrow mb-4">Step 2 of 2</p>
        <h1 className="display text-4xl mb-3">Payment.</h1>
        <p className="text-sm text-ink-500 mb-10">
          Order <span className="font-mono text-ink-700">{checkout.order.order_number}</span> is reserved —
          stock is held until you pay or cancel.
        </p>

        <div className="flex items-baseline justify-between gap-4 pb-5 mb-8 border-b border-line-strong">
          <span className="eyebrow">Amount due</span>
          <span className="display text-4xl tabular-nums">{inr(checkout.amount_to_pay)}</span>
        </div>

        <PaymentPanel
          orderId={checkout.order.id}
          clientSecret={checkout.client_secret}
          amount={checkout.amount_to_pay}
          mock={checkout.mock_payment}
          onPaid={handlePaid}
        />

        <p className="text-xs text-center text-ink-400 mt-8">
          Prefer to pay later? Your <Link to="/orders" className="link-rule text-ink-700">orders page</Link> can
          pay or cancel this order.
        </p>
      </div>
    )
  }

  // ── Address ───────────────────────────────────────────────────────────────
  if (!cart) return <PageLoader />

  if (cart.is_empty) return (
    <div className="max-w-xl mx-auto px-5 py-28 text-center">
      <h1 className="display text-4xl mb-3">Nothing to check out.</h1>
      <p className="text-ink-500 mb-8">Your cart is empty.</p>
      <Link to="/" className="btn-primary">Browse products</Link>
    </div>
  )

  return (
    <div className="max-w-6xl mx-auto px-5 sm:px-8 py-12">
      <Link to="/cart" className="inline-flex items-center gap-2 eyebrow mb-10 hover:text-ink transition-colors">
        <ArrowLeft className="w-3.5 h-3.5" /> Back to cart
      </Link>

      <p className="eyebrow mb-4">Step 1 of 2</p>
      <h1 className="display text-5xl mb-12">Where should it go?</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-5">
          <Field label="Full name"      name="full_name" value={form.full_name} onChange={handleChange} placeholder="Naresh S" required />
          <Field label="Address line 1" name="line1"     value={form.line1}     onChange={handleChange} placeholder="42 MG Road" required />
          <Field label="Address line 2" name="line2"     value={form.line2}     onChange={handleChange} placeholder="Apartment, suite (optional)" />

          <div className="grid grid-cols-2 gap-5">
            <Field label="City"  name="city"  value={form.city}  onChange={handleChange} placeholder="Chennai"    required />
            <Field label="State" name="state" value={form.state} onChange={handleChange} placeholder="Tamil Nadu" required />
          </div>
          <div className="grid grid-cols-2 gap-5">
            <Field label="Postal code" name="postal_code" value={form.postal_code} onChange={handleChange} placeholder="600001" required />
            <Field label="Phone"       name="phone"       value={form.phone}       onChange={handleChange} placeholder="+91-9876543210" />
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full py-3 mt-4">
            {loading ? <Spinner /> : 'Place order and continue to payment'}
          </button>
        </form>

        <div className="lg:col-span-1">
          <Summary cart={cart} />
        </div>
      </div>
    </div>
  )
}
