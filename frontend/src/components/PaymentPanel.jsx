import { useState } from 'react'
import { Elements, PaymentElement, useElements, useStripe } from '@stripe/react-stripe-js'
import { CreditCard, FlaskConical, AlertTriangle } from 'lucide-react'
import toast from 'react-hot-toast'
import { errorMessage, ordersAPI } from '../api/client'
import { getStripe, STRIPE_PUBLISHABLE_KEY } from '../lib/stripe'
import { inr } from '../lib/format'
import { Spinner } from './ui'

// The Stripe webhook flips the order to "paid" — usually within a second or two
async function waitUntilPaid(orderId, attempts = 10) {
  for (let i = 0; i < attempts; i++) {
    const { data } = await ordersAPI.get(orderId)
    if (data.status !== 'pending_payment') return data
    await new Promise(resolve => setTimeout(resolve, 1500))
  }
  return null
}

function StripeForm({ orderId, amount, onPaid }) {
  const stripe = useStripe()
  const elements = useElements()
  const [busy, setBusy] = useState(false)

  const pay = async (e) => {
    e.preventDefault()
    if (!stripe || !elements) return
    setBusy(true)
    try {
      const { error, paymentIntent } = await stripe.confirmPayment({
        elements,
        redirect: 'if_required',   // cards complete inline; redirect methods come back to /orders
        confirmParams: { return_url: `${window.location.origin}/orders` },
      })
      if (error) {
        toast.error(error.message || 'Payment failed')
        return
      }
      if (paymentIntent && ['succeeded', 'processing'].includes(paymentIntent.status)) {
        const order = await waitUntilPaid(orderId)
        if (!order) toast('Payment received — your order will update in a moment')
        onPaid(order)
      }
    } catch (err) {
      toast.error(errorMessage(err, 'Payment failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={pay} className="space-y-5">
      <PaymentElement />
      <button type="submit" disabled={!stripe || busy} className="btn-primary w-full py-3">
        {busy ? <Spinner /> : <><CreditCard className="w-4 h-4" /> Pay {inr(amount)}</>}
      </button>
    </form>
  )
}

function MockPayment({ orderId, amount, onPaid }) {
  const [busy, setBusy] = useState(false)

  const pay = async () => {
    setBusy(true)
    try {
      const { data } = await ordersAPI.mockPay(orderId)
      onPaid(data)
    } catch (err) {
      toast.error(errorMessage(err, 'Payment failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex gap-3 rounded-xl border border-clay-300 bg-clay-100/70 p-4 text-sm text-ink-700">
        <FlaskConical className="w-4 h-4 flex-shrink-0 mt-0.5 text-clay-500" />
        <p className="leading-relaxed">
          <span className="text-ink font-medium">Test mode.</span> Stripe is not configured on the server,
          so no card is charged. Add Stripe keys to enable real card payments.
        </p>
      </div>
      <button onClick={pay} disabled={busy} className="btn-primary w-full py-3">
        {busy ? <Spinner /> : <><CreditCard className="w-4 h-4" /> Simulate payment · {inr(amount)}</>}
      </button>
    </div>
  )
}

export default function PaymentPanel({ orderId, clientSecret, amount, mock, onPaid }) {
  if (mock) return <MockPayment orderId={orderId} amount={amount} onPaid={onPaid} />

  if (!STRIPE_PUBLISHABLE_KEY) {
    return (
      <div className="flex gap-3 rounded-xl border border-flag-up/30 bg-flag-up/5 p-4 text-sm text-flag-up">
        <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <p className="leading-relaxed">
          The server uses Stripe, but <code className="font-mono text-xs">VITE_STRIPE_PUBLISHABLE_KEY</code> is
          not set in <code className="font-mono text-xs">frontend/.env</code>. Add it and restart the dev server.
        </p>
      </div>
    )
  }

  return (
    <Elements
      stripe={getStripe()}
      options={{ clientSecret, appearance: { theme: 'flat', variables: { colorPrimary: '#4A5839', colorBackground: '#FDFCFA', fontFamily: 'Inter, system-ui, sans-serif', borderRadius: '12px' } } }}
    >
      <StripeForm orderId={orderId} amount={amount} onPaid={onPaid} />
    </Elements>
  )
}
