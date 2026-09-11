import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI, tokens } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!tokens.access()) {
      setLoading(false)
      return
    }
    let cancelled = false
    let retryTimer

    const load = async (attempt = 1) => {
      try {
        const { data } = await authAPI.me()
        if (!cancelled) setUser(data)
      } catch (err) {
        const status = err.response?.status
        if (status === 401 || status === 403) {
          tokens.clear()                     // the session really is invalid
        } else if (attempt < 3) {
          // API briefly unreachable (e.g. restarting) — keep the session and retry
          retryTimer = setTimeout(() => load(attempt + 1), 1500)
          return
        }
      }
      if (!cancelled) setLoading(false)
    }

    load()
    return () => {
      cancelled = true
      clearTimeout(retryTimer)
    }
  }, [])

  const login = async (email, password) => {
    const { data } = await authAPI.login({ email, password })
    tokens.set(data.access_token, data.refresh_token)
    const me = await authAPI.me()
    setUser(me.data)
    return me.data
  }

  const register = async (payload) => {
    await authAPI.register(payload)
    return login(payload.email, payload.password)
  }

  const logout = () => {
    tokens.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
