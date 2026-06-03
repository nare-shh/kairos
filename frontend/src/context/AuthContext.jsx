import { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]   = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('kairos_token')
    if (token) {
      authAPI.me()
        .then(r => setUser(r.data))
        .catch(() => localStorage.clear())
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email, password) => {
    const { data } = await authAPI.login({ email, password })
    localStorage.setItem('kairos_token',   data.access_token)
    localStorage.setItem('kairos_refresh', data.refresh_token)
    const me = await authAPI.me()
    setUser(me.data)
    return me.data
  }

  const register = async (payload) => {
    await authAPI.register(payload)
    return login(payload.email, payload.password)
  }

  const logout = () => {
    localStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
