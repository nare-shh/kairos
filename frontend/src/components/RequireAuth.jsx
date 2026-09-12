import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { PageLoader } from './ui'

// Route guard: sends signed-out users to /auth (and back afterwards)
export default function RequireAuth({ roles, children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <PageLoader />
  if (!user) return <Navigate to="/auth" replace state={{ from: location.pathname }} />
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="max-w-2xl mx-auto px-5 py-28 text-center">
        <p className="eyebrow mb-4">Restricted</p>
        <h1 className="display text-4xl mb-3">Sellers only.</h1>
        <p className="text-ink-500">This page is available to {roles.join(' and ')} accounts.</p>
      </div>
    )
  }
  return children
}
