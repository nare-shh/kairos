import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Zap, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { errorMessage } from '../api/client'
import { inputClass } from '../components/ui'
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
      toast.success(tab === 'login' ? 'Welcome back!' : 'Account created!')
      navigate(from, { replace: true })
    } catch (err) {
      toast.error(errorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-sm animate-slide-up">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-brand-600 flex items-center justify-center mx-auto mb-4">
            <Zap className="w-6 h-6 text-white" />
          </div>
          <h1 className="text-2xl font-bold">Kairos</h1>
          <p className="text-slate-500 text-sm mt-1">Intent-Driven Dynamic Pricing</p>
        </div>

        {/* Tabs */}
        <div className="flex bg-surface-800 border border-surface-700 rounded-xl p-1 mb-6">
          {['login', 'register'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors capitalize
                ${tab === t ? 'bg-surface-600 text-white' : 'text-slate-400 hover:text-white'}`}>
              {t === 'login' ? 'Sign In' : 'Sign Up'}
            </button>
          ))}
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">

          {tab === 'register' && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Full Name</label>
              <input name="full_name" value={form.full_name} onChange={set}
                placeholder="Naresh S" required className={inputClass} />
            </div>
          )}

          <div>
            <label className="block text-xs text-slate-400 mb-1">Email</label>
            <input name="email" type="email" value={form.email} onChange={set}
              placeholder="you@example.com" required autoComplete="email" className={inputClass} />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Password</label>
            <div className="relative">
              <input name="password" type={showPw ? 'text' : 'password'} value={form.password} onChange={set}
                placeholder={tab === 'register' ? 'Min 8 chars, 1 uppercase, 1 number' : '••••••••'}
                required autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                className={`${inputClass} pr-10`} />
              <button type="button" onClick={() => setShowPw(v => !v)} aria-label={showPw ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {tab === 'register' && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Account Type</label>
              <select name="role" value={form.role} onChange={set} className={inputClass}>
                <option value="customer">Customer — Browse & Buy</option>
                <option value="seller">Seller — List Products</option>
              </select>
            </div>
          )}

          <button type="submit" disabled={loading}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:opacity-60 rounded-xl font-medium transition-colors mt-2">
            {loading
              ? <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              : tab === 'login' ? 'Sign In' : 'Create Account'
            }
          </button>
        </form>

        {tab === 'login' && (
          <div className="mt-6 p-3 bg-surface-800 border border-surface-700 rounded-xl text-xs text-slate-500">
            <p className="font-medium text-slate-400 mb-2">Demo accounts <span className="font-normal">(after seeding — click to fill)</span></p>
            <div className="space-y-1">
              {DEMO_ACCOUNTS.map(a => (
                <button key={a.email} type="button"
                  onClick={() => setForm(f => ({ ...f, email: a.email, password: a.password }))}
                  className="w-full flex justify-between gap-2 px-2 py-1.5 rounded-lg hover:bg-surface-700 transition-colors text-left">
                  <span className="text-slate-400">{a.label}</span>
                  <span className="font-mono text-slate-300">{a.email}</span>
                </button>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
