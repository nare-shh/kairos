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

function Footer() {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 py-10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="display text-xl">Kairos</p>
          <p className="text-sm text-ink-500 mt-1">Prices that move with demand, in real time.</p>
        </div>
        <p className="eyebrow">Intent-driven pricing engine</p>
      </div>
    </footer>
  )
}

function NotFound() {
  return (
    <div className="max-w-3xl mx-auto px-5 py-28 text-center">
      <p className="eyebrow mb-4">Error 404</p>
      <h1 className="display text-5xl sm:text-6xl mb-4">This page moved on.</h1>
      <p className="text-ink-500 mb-8">The page you were looking for does not exist.</p>
      <Link to="/" className="btn-primary">Back to the store</Link>
    </div>
  )
}

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-paper-100 text-ink">
      <Navbar />
      <main className="flex-1">
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
      <Footer />
    </div>
  )
}
