import { Routes, Route, Link } from 'react-router-dom'
import Navbar from './components/Navbar'
import RequireAuth from './components/RequireAuth'
import Home from './pages/Home'
import ProductDetail from './pages/ProductDetail'
import Cart from './pages/Cart'
import Checkout from './pages/Checkout'
import Orders from './pages/Orders'
import Auth from './pages/Auth'
import Dashboard from './pages/Dashboard'

function NotFound() {
  return (
    <div className="text-center py-24">
      <p className="text-5xl font-black text-surface-600 mb-3">404</p>
      <p className="text-slate-400 mb-6">This page doesn't exist.</p>
      <Link to="/" className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 rounded-xl text-sm font-medium transition-colors">
        Back to the store
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-surface-900 text-white">
      <Navbar />
      <main>
        <Routes>
          <Route path="/"               element={<Home />} />
          <Route path="/products/:id"   element={<ProductDetail />} />
          <Route path="/cart"           element={<Cart />} />
          <Route path="/checkout"       element={<RequireAuth><Checkout /></RequireAuth>} />
          <Route path="/orders"         element={<RequireAuth><Orders /></RequireAuth>} />
          <Route path="/auth"           element={<Auth />} />
          <Route path="/dashboard"      element={<RequireAuth roles={['seller', 'admin']}><Dashboard /></RequireAuth>} />
          <Route path="*"               element={<NotFound />} />
        </Routes>
      </main>
    </div>
  )
}
