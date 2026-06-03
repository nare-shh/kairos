import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CreditCard, CheckCircle2, ArrowLeft } from 'lucide-react'
import { ordersAPI } from '../api/client'
import { useCart } from '../context/CartContext'
import toast from 'react-hot-toast'

const Field = ({ label, name, value, onChange, placeholder, required }) => (
  <div>
    <label className="block text-xs text-slate-400 mb-1">{label}</label>
    <input name={name} value={value} onChange={onChange} placeholder={placeholder} required={required}
      className="w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors placeholder:text-slate-600" />
  </div>
)

export default function Checkout() {
  const navigate = useNavigate()
  const { fetchCart } = useCart()
  const [loading,  setLoading]  = useState(false)
  const [complete, setComplete] = useState(false)
  const [order,    setOrder]    = useState(null)

  const [form, setForm] = useState({
    full_name: '', line1: '', line2: '', city: '',
    state: '', postal_code: '', country: 'IN', phone: '',
  })

  const handleChange = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await ordersAPI.checkout({
        shipping_address: form,
        notes: '',
      })
      setOrder(data)
      setComplete(true)
      await fetchCart()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Checkout failed. Check your cart.')
    } finally {
      setLoading(false)
    }
  }

  if (complete && order) return (
    <div className="max-w-lg mx-auto px-4 py-20 text-center animate-slide-up">
      <CheckCircle2 className="w-16 h-16 text-emerald-500 mx-auto mb-5" />
      <h1 className="text-2xl font-bold mb-2">Order Placed!</h1>
      <p className="text-slate-400 mb-1">Order Number</p>
      <p className="text-xl font-mono font-bold text-brand-500 mb-6">{order.order.order_number}</p>

      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 text-left mb-6 space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Subtotal</span>
          <span>₹{parseFloat(order.order.subtotal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Tax</span>
          <span>₹{parseFloat(order.order.tax_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex justify-between font-bold pt-2 border-t border-surface-700">
          <span>Total Charged</span>
          <span>₹{parseFloat(order.amount_to_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
      </div>

      <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3 text-sm text-amber-400 mb-6">
        Payment ID: <span className="font-mono text-xs">{order.payment_intent_id}</span>
      </div>

      <button onClick={() => navigate('/')}
        className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl font-medium transition-colors">
        Continue Shopping
      </button>
    </div>
  )

  return (
    <div className="max-w-xl mx-auto px-4 sm:px-6 py-10">
      <button onClick={() => navigate('/cart')}
        className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-white mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to cart
      </button>

      <h1 className="text-2xl font-bold mb-8 flex items-center gap-2">
        <CreditCard className="w-6 h-6" /> Checkout
      </h1>

      <form onSubmit={handleSubmit} className="space-y-4">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Shipping Address</h2>

        <Field label="Full Name"    name="full_name"    value={form.full_name}    onChange={handleChange} placeholder="Naresh S" required />
        <Field label="Address Line 1" name="line1"      value={form.line1}        onChange={handleChange} placeholder="42 MG Road" required />
        <Field label="Address Line 2" name="line2"      value={form.line2}        onChange={handleChange} placeholder="Apartment, suite (optional)" />

        <div className="grid grid-cols-2 gap-3">
          <Field label="City"    name="city"        value={form.city}        onChange={handleChange} placeholder="Chennai"   required />
          <Field label="State"   name="state"       value={form.state}       onChange={handleChange} placeholder="Tamil Nadu" required />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Postal Code" name="postal_code" value={form.postal_code} onChange={handleChange} placeholder="600001" required />
          <Field label="Phone"       name="phone"       value={form.phone}       onChange={handleChange} placeholder="+91-9876543210" />
        </div>

        <div className="pt-2">
          <div className="bg-surface-700 border border-surface-600 rounded-xl p-4 mb-4">
            <p className="text-xs text-slate-500 mb-1">Payment</p>
            <p className="text-sm text-slate-400 flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-brand-500" />
              Powered by Stripe — your card is never stored on our servers.
            </p>
          </div>

          <button type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-3 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 rounded-xl font-medium transition-colors">
            {loading ? (
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <><CreditCard className="w-4 h-4" /> Place Order</>
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
