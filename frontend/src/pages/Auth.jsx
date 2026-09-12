import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { FormField, Spinner, inputClass } from '../components/ui'
import toast from 'react-hot-toast'

// Created by `python -m app.seed`
const DEMO_ACCOUNTS = [
  { label: 'Seller',   email: 'naresh@kairos.dev',   password: 'Kairos123' },
  { label: 'Customer', email: 'customer@kairos.dev', password: 'Customer123' },
  { label: 'Admin',    email: 'admin@kairos.dev',    password: 'Admin1234' },
]

export default function Auth() {
  const { user, login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from || '/'

  const [tab,     setTab]     = useState('login')
  const [loading, setLoading] = useState(false)
  const [showPw,  setShowPw]  = useState(false)

  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'customer' })
  const set = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  if (user) return <Navigate to={from} replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      if (tab === 'login') {
        await login(form.email, form.password)
      } else {
        await register({ email: form.email, password: form.password, full_name: form.full_name, role: form.role })
      }
      toast.success(tab === 'login' ? 'Welcome back' : 'Account created')
      navigate(from, { replace: true })
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto px-5 py-20 animate-slide-up">
      <p className="eyebrow mb-4">{tab === 'login' ? 'Sign in' : 'Create account'}</p>
      <h1 className="display text-4xl sm:text-5xl leading-[1.05] mb-10">
        {tab === 'login' ? 'Welcome back.' : 'Start selling, or shopping.'}
      </h1>

      {/* Tabs */}
      <div className="flex gap-6 border-b border-line mb-8">
        {[['login', 'Sign in'], ['register', 'Sign up']].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`pb-3 -mb-px text-sm transition-colors border-b ${
              tab === key ? 'border-ink text-ink' : 'border-transparent text-ink-500 hover:text-ink'
            }`}>
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {tab === 'register' && (
          <FormField label="Full name">
            <input name="full_name" value={form.full_name} onChange={set} required placeholder="Naresh S" className={inputClass} />
          </FormField>
        )}

        <FormField label="Email">
          <input name="email" type="email" value={form.email} onChange={set} required autoComplete="email"
            placeholder="you@example.com" className={inputClass} />
        </FormField>

        <FormField label="Password" hint={tab === 'register' ? 'At least 8 characters, one uppercase letter and one number' : undefined}>
          <div className="relative">
            <input name="password" type={showPw ? 'text' : 'password'} value={form.password} onChange={set} required
              autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
              placeholder="••••••••" className={`${inputClass} pr-10`} />
            <button type="button" onClick={() => setShowPw(v => !v)}
              aria-label={showPw ? 'Hide password' : 'Show password'}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink transition-colors">
              {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </FormField>

        {tab === 'register' && (
          <FormField label="Account type">
            <select name="role" value={form.role} onChange={set} className={inputClass}>
              <option value="customer">Customer — browse and buy</option>
              <option value="seller">Seller — list products</option>
            </select>
          </FormField>
        )}

        <button type="submit" disabled={loading} className="btn-primary w-full py-3">
          {loading ? <Spinner /> : tab === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>

      {tab === 'login' && (
        <div className="mt-10 pt-6 border-t border-line">
          <p className="eyebrow mb-3">Demo accounts — tap to fill</p>
          <ul className="divide-y divide-line">
            {DEMO_ACCOUNTS.map(a => (
              <li key={a.email}>
                <button type="button"
                  onClick={() => setForm(f => ({ ...f, email: a.email, password: a.password }))}
                  className="w-full flex items-center justify-between gap-3 py-3 text-left group">
                  <span className="eyebrow group-hover:text-ink transition-colors">{a.label}</span>
                  <span className="text-sm text-ink-700">{a.email}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
