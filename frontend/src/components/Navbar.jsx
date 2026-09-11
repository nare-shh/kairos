import { Link, NavLink, useNavigate } from 'react-router-dom'
import { ShoppingCart, Zap, LogOut, User, BarChart2, Receipt } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'

const navLink = ({ isActive }) =>
  `hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
    isActive ? 'text-white bg-surface-700' : 'text-slate-400 hover:text-white hover:bg-surface-700'
  }`

export default function Navbar() {
  const { user, logout } = useAuth()
  const { itemCount }    = useCart()
  const navigate         = useNavigate()

  const handleLogout = () => { logout(); navigate('/') }
  const canSell = user?.role === 'seller' || user?.role === 'admin'

  return (
    <nav className="sticky top-0 z-50 border-b border-surface-700 bg-surface-900/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">

        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-bold tracking-tight">
            Kairos
            <span className="ml-1.5 text-xs font-normal text-slate-500 hidden sm:inline">
              Dynamic Pricing
            </span>
          </span>
        </Link>

        {/* Right side */}
        <div className="flex items-center gap-2">

          {canSell && (
            <NavLink to="/dashboard" className={navLink}>
              <BarChart2 className="w-4 h-4" />
              Dashboard
            </NavLink>
          )}

          {user && (
            <NavLink to="/orders" className={navLink}>
              <Receipt className="w-4 h-4" />
              Orders
            </NavLink>
          )}

          {user ? (
            <>
              <span className="hidden md:flex items-center gap-2 text-sm text-slate-400 px-2">
                {user.full_name || user.email.split('@')[0]}
                {user.role !== 'customer' && (
                  <span className="px-1.5 py-0.5 rounded bg-brand-600/20 text-brand-500 text-[10px] font-semibold uppercase tracking-wide">
                    {user.role}
                  </span>
                )}
              </span>
              <button onClick={handleLogout} aria-label="Sign out" title="Sign out"
                className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-700 transition-colors">
                <LogOut className="w-4 h-4" />
              </button>
            </>
          ) : (
            <Link to="/auth"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-surface-700 transition-colors">
              <User className="w-4 h-4" />
              Sign in
            </Link>
          )}

          {/* Cart */}
          <Link to="/cart" aria-label="Cart" className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-surface-700 transition-colors">
            <ShoppingCart className="w-5 h-5" />
            {itemCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-brand-600 rounded-full text-[10px] font-bold flex items-center justify-center text-white">
                {itemCount > 9 ? '9+' : itemCount}
              </span>
            )}
          </Link>

        </div>
      </div>
    </nav>
  )
}
