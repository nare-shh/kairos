import { Navigate, useLocation } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
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
      <div className="text-center py-24 text-slate-500">
        <ShieldAlert className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>This page is only available to {roles.join(' / ')} accounts.</p>
      </div>
    )
  }
  return children
}
