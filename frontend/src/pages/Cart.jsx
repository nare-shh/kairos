import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShoppingCart, Trash2, ArrowRight, Package } from 'lucide-react'
import { useCart } from '../context/CartContext'
import { useAuth } from '../context/AuthContext'
import { intentAPI } from '../api/client'
import toast from 'react-hot-toast'

export default function Cart() {
  const { cart, fetchCart, removeFromCart } = useCart()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user) { setLoading(false); return }
    fetchCart().finally(() => setLoading(false))
  }, [user])

  const handleRemove = (productId) => {
    intentAPI.track({ product_id: productId, event_type: 'CartRemoved', session_id: `sess-${Date.now()}` }).catch(() => {})
    removeFromCart(productId)
  }

  if (!user) return (
    <div className="max-w-2xl mx-auto px-4 py-24 text-center">
      <ShoppingCart className="w-12 h-12 mx-auto mb-4 text-slate-600" />
      <h2 className="text-xl font-semibold mb-2">Sign in to view your cart</h2>
      <p className="text-slate-500 mb-6">You need to be logged in to add items to your cart.</p>
      <Link to="/auth" className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
        Sign in
      </Link>
    </div>
  )

  if (loading) return (
    <div className="max-w-2xl mx-auto px-4 py-16">
      {[...Array(3)].map((_, i) => <div key={i} className="h-20 bg-surface-700 rounded-xl mb-3 animate-pulse" />)}
    </div>
  )

  if (!cart || cart.is_empty) return (
    <div className="max-w-2xl mx-auto px-4 py-24 text-center">
      <Package className="w-12 h-12 mx-auto mb-4 text-slate-600" />
      <h2 className="text-xl font-semibold mb-2">Your cart is empty</h2>
      <p className="text-slate-500 mb-6">Add some products to get started.</p>
      <Link to="/" className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
        Browse Products
      </Link>
    </div>
  )

  const subtotal = cart.items.reduce((s, i) => s + parseFloat(i.total_price), 0)
  const tax = subtotal * 0.18
  const total = subtotal + tax

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-10">
      <h1 className="text-2xl font-bold mb-8 flex items-center gap-2">
        <ShoppingCart className="w-6 h-6" /> Cart
        <span className="text-sm font-normal text-slate-500">({cart.item_count} items)</span>
      </h1>

      {/* Items */}
      <div className="space-y-3 mb-8">
        {cart.items.map(item => (
          <div key={item.product_id} className="flex items-center gap-4 p-4 bg-surface-800 border border-surface-700 rounded-xl">
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-brand-600 to-purple-600 flex items-center justify-center text-lg font-black text-white/30 flex-shrink-0">
              {item.product_name[0]}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-sm truncate">{item.product_name}</p>
              <p className="text-xs text-slate-500">{item.sku}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-sm font-semibold tabular-nums">
                ₹{parseFloat(item.total_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
              <p className="text-xs text-slate-500">
                {item.quantity} × ₹{parseFloat(item.unit_price).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </p>
            </div>
            <button onClick={() => handleRemove(item.product_id)}
              className="p-1.5 rounded-lg text-slate-600 hover:text-red-400 hover:bg-red-400/10 transition-colors flex-shrink-0">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="bg-surface-800 border border-surface-700 rounded-xl p-5 space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Subtotal</span>
          <span className="tabular-nums">₹{subtotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Tax (18% GST)</span>
          <span className="tabular-nums">₹{tax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Shipping</span>
          <span className="text-emerald-400">Free</span>
        </div>
        <div className="pt-3 border-t border-surface-700 flex justify-between font-bold text-lg">
          <span>Total</span>
          <span className="tabular-nums">₹{total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
        </div>

        <button
          onClick={() => navigate('/checkout')}
          className="w-full flex items-center justify-center gap-2 py-3 bg-brand-600 hover:bg-brand-700 rounded-xl font-medium transition-colors mt-2">
          Proceed to Checkout
          <ArrowRight className="w-4 h-4" />
        </button>
        <p className="text-xs text-center text-slate-600">
          Prices shown reflect Kairos dynamic pricing at time of adding to cart.
        </p>
      </div>
    </div>
  )
}
