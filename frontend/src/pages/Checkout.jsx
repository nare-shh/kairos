import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { CreditCard, CheckCircle2, ArrowLeft, MapPin, Package } from 'lucide-react'
import toast from 'react-hot-toast'
import { errorMessage, ordersAPI, trackIntent } from '../api/client'
import { useCart } from '../context/CartContext'
import PaymentPanel from '../components/PaymentPanel'
import OrderStatusBadge from '../components/OrderStatusBadge'
import { FormField, inputClass, primaryButton, secondaryButton, Spinner } from '../components/ui'
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
    <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 space-y-3">
      <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Order Summary</h2>
      {cart.items.map(i => (
        <div key={i.product_id} className="flex justify-between gap-3 text-sm">
          <span className="text-slate-300 truncate">{i.quantity} × {i.product_name}</span>
          <span className="tabular-nums flex-shrink-0">{inr(i.total_price)}</span>
        </div>
      ))}
      <div className="pt-3 border-t border-surface-700 space-y-1.5 text-sm">
        <div className="flex justify-between"><span className="text-slate-400">Subtotal</span><span className="tabular-nums">{inr(subtotal)}</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Tax (18% GST)</span><span className="tabular-nums">{inr(tax)}</span></div>
        <div className="flex justify-between"><span className="text-slate-400">Shipping</span><span className="text-emerald-400">Free</span></div>
        <div className="flex justify-between font-bold text-base pt-1"><span>Total</span><span className="tabular-nums">{inr(subtotal + tax)}</span></div>
      </div>
      <p className="text-[11px] text-slate-600">Live Kairos prices — locked in when you place the order.</p>
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
  // order is an abandonment. (The mounted-ref dance ignores React StrictMode's
  // simulated unmount in development.)
  const startedFor = useRef(null)
  const stepRef = useRef(step)
  const mounted = useRef(false)
  stepRef.current = step

  useEffect(() => { fetchCart() }, [fetchCart])

  useEffect(() => {
    if (!cart || cart.is_empty || startedFor.current) return
    startedFor.current = cart.items.map(i => i.product_id)
    // The signal can move the price itself — re-read the cart so the summary
    // shows exactly what "Place Order" will charge
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
      <div className="max-w-lg mx-auto px-4 py-20 text-center animate-slide-up">
        <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-5" />
        <h1 className="text-2xl font-bold mb-2">Order Placed!</h1>
        <p className="text-slate-400 mb-1">Order Number</p>
        <p className="text-xl font-mono font-bold text-brand-500 mb-3">{order.order_number}</p>
        <div className="mb-6"><OrderStatusBadge status={order.status} /></div>

        <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 text-left mb-6 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Subtotal</span>
            <span>{inr(order.subtotal)}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-slate-400">Tax</span>
            <span>{inr(order.tax_amount)}</span>
          </div>
          <div className="flex justify-between font-bold pt-2 border-t border-surface-700">
            <span>Total Charged</span>
            <span>{inr(order.total_amount)}</span>
          </div>
        </div>

        <div className="flex gap-3 justify-center">
          <button onClick={() => navigate('/orders')} className={secondaryButton}>View orders</button>
          <button onClick={() => navigate('/')} className={primaryButton}>Continue Shopping</button>
        </div>
      </div>
    )
  }

  // ── Payment ───────────────────────────────────────────────────────────────
  if (step === 'payment' && checkout) {
    return (
      <div className="max-w-lg mx-auto px-4 sm:px-6 py-10 animate-slide-up">
        <h1 className="text-2xl font-bold mb-2 flex items-center gap-2">
          <CreditCard className="w-6 h-6" /> Payment
        </h1>
        <p className="text-sm text-slate-400 mb-6">
          Order <span className="font-mono text-brand-500">{checkout.order.order_number}</span> is reserved —
          stock is held until you pay or cancel.
        </p>

        <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 mb-6 flex justify-between items-center">
          <span className="text-slate-400">Amount due</span>
          <span className="text-2xl font-bold tabular-nums">{inr(checkout.amount_to_pay)}</span>
        </div>

        <PaymentPanel
          orderId={checkout.order.id}
          clientSecret={checkout.client_secret}
          amount={checkout.amount_to_pay}
          mock={checkout.mock_payment}
          onPaid={handlePaid}
        />

        <p className="text-xs text-center text-slate-500 mt-6">
          Want to pay later? <Link to="/orders" className="text-brand-500 hover:underline">Your orders</Link> page
          lets you pay or cancel.
        </p>
      </div>
    )
  }

  // ── Address ───────────────────────────────────────────────────────────────
  if (!cart) return <div className="flex justify-center py-24"><Spinner className="w-6 h-6" /></div>

  if (cart.is_empty) return (
    <div className="max-w-2xl mx-auto px-4 py-24 text-center">
      <Package className="w-12 h-12 mx-auto mb-4 text-slate-600" />
      <h2 className="text-xl font-semibold mb-2">Nothing to check out</h2>
      <p className="text-slate-500 mb-6">Your cart is empty.</p>
      <Link to="/" className={primaryButton}>Browse Products</Link>
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10">
      <button onClick={() => navigate('/cart')}
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to cart
      </button>

      <h1 className="text-2xl font-bold mb-8 flex items-center gap-2">
        <CreditCard className="w-6 h-6" /> Checkout
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-8">
        <form onSubmit={handleSubmit} className="space-y-4 md:col-span-3">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-2">
            <MapPin className="w-4 h-4" /> Shipping Address
          </h2>

          <Field label="Full Name"      name="full_name" value={form.full_name} onChange={handleChange} placeholder="Naresh S" required />
          <Field label="Address Line 1" name="line1"     value={form.line1}     onChange={handleChange} placeholder="42 MG Road" required />
          <Field label="Address Line 2" name="line2"     value={form.line2}     onChange={handleChange} placeholder="Apartment, suite (optional)" />

          <div className="grid grid-cols-2 gap-3">
            <Field label="City"  name="city"  value={form.city}  onChange={handleChange} placeholder="Chennai"    required />
            <Field label="State" name="state" value={form.state} onChange={handleChange} placeholder="Tamil Nadu" required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Postal Code" name="postal_code" value={form.postal_code} onChange={handleChange} placeholder="600001" required />
            <Field label="Phone"       name="phone"       value={form.phone}       onChange={handleChange} placeholder="+91-9876543210" />
          </div>

          <button type="submit" disabled={loading} className={`${primaryButton} w-full py-3 mt-2`}>
            {loading ? <Spinner /> : <>Place Order &amp; Continue to Payment</>}
          </button>
        </form>

        <div className="md:col-span-2">
          <Summary cart={cart} />
        </div>
      </div>
    </div>
  )
}
