import { loadStripe } from '@stripe/stripe-js'

// Only needed when the backend has a real STRIPE_SECRET_KEY.
// Without Stripe, checkout uses mock payments and Stripe.js is never loaded.
export const STRIPE_PUBLISHABLE_KEY = import.meta.env.VITE_STRIPE_PUBLISHABLE_KEY || ''

let stripePromise = null

export function getStripe() {
  if (!STRIPE_PUBLISHABLE_KEY) return null
  if (!stripePromise) stripePromise = loadStripe(STRIPE_PUBLISHABLE_KEY)
  return stripePromise
}
