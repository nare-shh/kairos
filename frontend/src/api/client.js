import axios from 'axios'

// Dev: the API runs on :8000. Production: the API serves this app, so it's the same origin.
// VITE_API_URL overrides both (e.g. when the frontend is hosted separately, like on Vercel).
const DEFAULT_API = import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin
const BASE = (import.meta.env.VITE_API_URL || DEFAULT_API).replace(/\/$/, '')

const TOKEN_KEY = 'kairos_token'
const REFRESH_KEY = 'kairos_refresh'
const SESSION_KEY = 'kairos_session'

export const tokens = {
  access:  () => localStorage.getItem(TOKEN_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access, refresh) => {
    localStorage.setItem(TOKEN_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT on every request
api.interceptors.request.use(cfg => {
  const token = tokens.access()
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-refresh token on 401 — concurrent requests share one refresh call
// (not for login/register/refresh themselves — a 401 there is the real answer)
const NO_REFRESH_PATHS = ['/auth/login', '/auth/register', '/auth/refresh']
let refreshing = null
api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    const refresh = tokens.refresh()
    const isAuthCall = NO_REFRESH_PATHS.some(path => original?.url?.startsWith(path))
    if (err.response?.status === 401 && refresh && original && !original._retry && !isAuthCall) {
      original._retry = true
      try {
        if (!refreshing) {
          refreshing = axios
            .post(`${BASE}/api/v1/auth/refresh`, { refresh_token: refresh })
            .finally(() => { refreshing = null })
        }
        const { data } = await refreshing
        tokens.set(data.access_token)
        original.headers.Authorization = `Bearer ${data.access_token}`
        return api(original)
      } catch (refreshErr) {
        // Only an explicit rejection ends the session — a network blip shouldn't
        const status = refreshErr.response?.status
        if (status === 401 || status === 403) {
          tokens.clear()
          window.location.href = '/auth'
        }
      }
    }
    return Promise.reject(err)
  }
)

export const WS_BASE = BASE.replace('https://', 'wss://').replace('http://', 'ws://')

// FastAPI returns `detail` as a string, or as a list of validation errors (422)
export function errorMessage(err, fallback = 'Something went wrong') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    return detail.map(d => (d.msg || '').replace(/^Value error, /, '')).join('; ')
  }
  if (err?.response?.status === 429) return 'Too many requests — please slow down'
  if (!err?.response) return 'Cannot reach the Kairos API — is the backend running?'
  return fallback
}

// One id per browser tab — lets the engine count unique viewers
export function sessionId() {
  try {
    let id = sessionStorage.getItem(SESSION_KEY)
    if (!id) {
      id = `sess-${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`
      sessionStorage.setItem(SESSION_KEY, id)
    }
    return id
  } catch {
    return 'sess-anonymous'
  }
}

// Fire-and-forget demand signal for the pricing engine
export function trackIntent(product_id, event_type, metadata = {}) {
  const path = tokens.access() ? '/intent/track/authenticated' : '/intent/track'
  return api
    .post(path, { product_id, event_type, session_id: sessionId(), metadata })
    .catch(() => undefined)
}

// ── API helpers ───────────────────────────────────────────────────────────────
export const productsAPI = {
  list:         (params)   => api.get('/products', { params }),
  get:          (id)       => api.get(`/products/${id}`),
  mine:         (params)   => api.get('/products/mine', { params }),
  trending:     (limit = 4) => api.get('/products/trending', { params: { limit } }),
  priceHistory: (id)       => api.get(`/products/${id}/price-history`),
  events:       (id)       => api.get(`/products/${id}/events`),
  create:       (data)     => api.post('/products', data),
  update:       (id, data) => api.patch(`/products/${id}`, data),
  changePrice:  (id, data) => api.put(`/products/${id}/price`, data),
  adjustStock:  (id, data) => api.patch(`/products/${id}/stock`, data),
  activate:     (id)       => api.post(`/products/${id}/activate`),
  deactivate:   (id)       => api.post(`/products/${id}/deactivate`),
  remove:       (id)       => api.delete(`/products/${id}`),
}

export const categoriesAPI = {
  list:   ()     => api.get('/categories'),
  create: (data) => api.post('/categories', data),
}

export const authAPI = {
  login:    (data) => api.post('/auth/login',    data),
  register: (data) => api.post('/auth/register', data),
  me:       ()     => api.get('/auth/me'),
}

export const cartAPI = {
  get:    ()     => api.get('/cart'),
  add:    (data) => api.post('/cart',  data),
  update: (data) => api.patch('/cart', data),
  clear:  ()     => api.delete('/cart'),
}

export const intentAPI = {
  score: (id) => api.get(`/intent/score/${id}`),
}

export const ordersAPI = {
  checkout:  (data)         => api.post('/orders/checkout', data),
  list:      (params)       => api.get('/orders', { params }),
  all:       (params)       => api.get('/orders/all', { params }),
  get:       (id)           => api.get(`/orders/${id}`),
  payment:   (id)           => api.get(`/orders/${id}/payment`),
  cancel:    (id)           => api.post(`/orders/${id}/cancel`),
  mockPay:   (id)           => api.post(`/orders/${id}/mock-payment`),
  setStatus: (id, status)   => api.patch(`/orders/${id}/status`, { status }),
}
