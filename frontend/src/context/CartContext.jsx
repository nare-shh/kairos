import { createContext, useContext, useState, useCallback } from 'react'
import { cartAPI } from '../api/client'
import toast from 'react-hot-toast'

const CartContext = createContext(null)

export function CartProvider({ children }) {
  const [cart, setCart] = useState(null)

  const fetchCart = useCallback(async () => {
    try {
      const { data } = await cartAPI.get()
      setCart(data)
    } catch {
      setCart(null)
    }
  }, [])

  const addToCart = async (product_id, quantity = 1) => {
    try {
      const { data } = await cartAPI.add({ product_id, quantity })
      setCart(data)
      toast.success('Added to cart')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not add to cart')
    }
  }

  const removeFromCart = async (product_id) => {
    try {
      const { data } = await cartAPI.update({ product_id, quantity: 0 })
      setCart(data)
    } catch {}
  }

  const clearCart = async () => {
    await cartAPI.clear()
    setCart(null)
  }

  const itemCount = cart?.item_count ?? 0

  return (
    <CartContext.Provider value={{ cart, itemCount, fetchCart, addToCart, removeFromCart, clearCart }}>
      {children}
    </CartContext.Provider>
  )
}

export const useCart = () => useContext(CartContext)
