import { Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { useAuth } from './context/AuthContext'
import { useCart } from './context/CartContext'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import ProductDetail from './pages/ProductDetail'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'

export default function App() {
  const { user } = useAuth()
  const { fetchCart } = useCart()

  // Load cart whenever user changes
  useEffect(() => {
    if (user) fetchCart()
  }, [user])

  return (
    <div className="min-h-screen bg-surface-900 text-white">
      <Navbar />
      <main>
        <Routes>
          <Route path="/"               element={<Home />} />
          <Route path="/products/:id"   element={<ProductDetail />} />
          <Route path="/cart"           element={<Cart />} />
          <Route path="/checkout"       element={<Checkout />} />
          <Route path="/auth"           element={<Auth />} />
          <Route path="/dashboard"      element={<Dashboard />} />
          <Route path="*"               element={<Home />} />
        </Routes>
      </main>
    </div>
  )
}
