import { Link, NavLink, useNavigate } from 'react-router-dom'
import { ShoppingCart, LogOut, Receipt, BarChart2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useCart } from '../context/CartContext'

const navLink = ({ isActive }) =>
  `hidden sm:flex items-center gap-1.5 px-3 py-1.5 text-[11px] uppercase tracking-caps transition-colors ${
    isActive ? 'text-ink' : 'text-ink-500 hover:text-ink'
  }`

export default function Navbar() {
  const { user, logout } = useAuth()
  const { itemCount }    = useCart()
  const navigate         = useNavigate()

  const handleLogout = () => { logout(); navigate('/') }
  const canSell = user?.role === 'seller' || user?.role === 'admin'

  return (
    <nav className="sticky top-0 z-50 border-b border-line bg-paper-100/85 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between gap-4">

        {/* Wordmark */}
        <Link to="/" className="flex items-baseline gap-2.5">
          <span className="display text-2xl leading-none">Kairos</span>
          <span className="eyebrow hidden sm:inline">Dynamic pricing</span>
        </Link>

        <div className="flex items-center gap-1">
          {canSell && (
            <NavLink to="/dashboard" className={navLink}>
              <BarChart2 className="w-3.5 h-3.5" /> Dashboard
            </NavLink>
          )}
          {user && (
            <NavLink to="/orders" className={navLink}>
              <Receipt className="w-3.5 h-3.5" /> Orders
            </NavLink>
          )}

          {user ? (
            <>
              <span className="hidden md:flex items-center gap-2 text-sm text-ink-700 pl-3 pr-1">
                {user.full_name || user.email.split('@')[0]}
                {user.role !== 'customer' && (
                  <span className="px-1.5 py-0.5 rounded bg-sage-100 text-sage-700 text-[10px] uppercase tracking-caps">
                    {user.role}
                  </span>
                )}
              </span>
              <button onClick={handleLogout} aria-label="Sign out" title="Sign out" className="btn-quiet">
                <LogOut className="w-4 h-4" />
              </button>
            </>
          ) : (
            <Link to="/auth" className="btn-primary px-4 py-2">Sign in</Link>
          )}

          <Link to="/cart" aria-label="Cart" className="btn-quiet relative">
            <ShoppingCart className="w-[18px] h-[18px]" />
            {itemCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-sage-900 text-paper-50 rounded-full text-[10px] font-semibold flex items-center justify-center">
                {itemCount > 9 ? '9+' : itemCount}
              </span>
            )}
          </Link>
        </div>
      </div>
    </nav>
  )
}
