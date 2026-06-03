import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Zap, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import toast from 'react-hot-toast'

export default function Auth() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [tab,     setTab]     = useState('login')
  const [loading, setLoading] = useState(false)
  const [showPw,  setShowPw]  = useState(false)

  const [form, setForm] = useState({ email: '', password: '', full_name: '', role: 'customer' })
  const set = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

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
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
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
                placeholder="Naresh S" required
                className="w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors placeholder:text-slate-600" />
            </div>
          )}

          <div>
            <label className="block text-xs text-slate-400 mb-1">Email</label>
            <input name="email" type="email" value={form.email} onChange={set}
              placeholder="you@example.com" required autoComplete="email"
              className="w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors placeholder:text-slate-600" />
          </div>

          <div>
            <label className="block text-xs text-slate-400 mb-1">Password</label>
            <div className="relative">
              <input name="password" type={showPw ? 'text' : 'password'} value={form.password} onChange={set}
                placeholder={tab === 'register' ? 'Min 8 chars, 1 uppercase, 1 number' : '••••••••'}
                required autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                className="w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors placeholder:text-slate-600 pr-10" />
              <button type="button" onClick={() => setShowPw(v => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
                {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {tab === 'register' && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Account Type</label>
              <select name="role" value={form.role} onChange={set}
                className="w-full px-3 py-2.5 bg-surface-700 border border-surface-600 rounded-xl text-sm focus:outline-none focus:border-brand-600 transition-colors">
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
          <div className="mt-6 p-3 bg-surface-800 border border-surface-700 rounded-xl text-xs text-slate-500 space-y-1">
            <p className="font-medium text-slate-400">Demo credentials</p>
            <p>Email: <span className="text-slate-300 font-mono">naresh@kairos.dev</span></p>
            <p>Password: <span className="text-slate-300 font-mono">Kairos123</span></p>
          </div>
        )}

      </div>
    </div>
  )
}
