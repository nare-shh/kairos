import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { cartAPI, errorMessage, trackIntent } from '../api/client'
import { useAuth } from './AuthContext'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [cart, setCart] = useState(null)

  const fetchCart = useCallback(async () => {
    try {
      const { data } = await cartAPI.get()
      setCart(data)
      return data
    } catch {
      setCart(null)
      return null
    }
  }, [])

  // Load the cart whenever the signed-in user changes; forget it on logout
  useEffect(() => {
    if (user) fetchCart()
    else setCart(null)
  }, [user, fetchCart])

  const addToCart = async (product_id, quantity = 1) => {
    if (!user) {
      toast('Sign in to add items to your cart')
      navigate('/auth', { state: { from: `/products/${product_id}` } })
      return false
    }
    try {
      // Record the demand signal FIRST, so the price saved in the cart already
      // reflects it (otherwise the cart immediately claims the item was repriced)
      await trackIntent(product_id, 'CartAdded')
      const { data } = await cartAPI.add({ product_id, quantity })
      setCart(data)
      toast.success('Added to cart')
      return true
    } catch (e) {
      toast.error(errorMessage(e, 'Could not add to cart'))
      return false
    }
  }

  const updateQuantity = async (product_id, quantity) => {
    try {
      const { data } = await cartAPI.update({ product_id, quantity })
      setCart(data)
      return true
    } catch (e) {
      toast.error(errorMessage(e, 'Could not update cart'))
      return false
    }
  }

  const removeFromCart = async (product_id) => {
    if (await updateQuantity(product_id, 0)) trackIntent(product_id, 'CartRemoved')
  }

  const clearCart = async () => {
    await cartAPI.clear()
    setCart(null)
  }

  const itemCount = cart?.item_count ?? 0

  return (
    <CartContext.Provider value={{ cart, itemCount, fetchCart, addToCart, updateQuantity, removeFromCart, clearCart }}>
      {children}
    </CartContext.Provider>
  )
}

export const useCart = () => useContext(CartContext)
