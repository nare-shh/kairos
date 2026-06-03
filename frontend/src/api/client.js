import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'https://kairos-production-a171.up.railway.app'

export const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT on every request
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('kairos_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-refresh token on 401
api.interceptors.response.use(
  res => res,
  async err => {
    const original = err.config
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true
      const refresh = localStorage.getItem('kairos_refresh')
      if (refresh) {
        try {
          const { data } = await axios.post(`${BASE}/api/v1/auth/refresh`, { refresh_token: refresh })
          localStorage.setItem('kairos_token', data.access_token)
          original.headers.Authorization = `Bearer ${data.access_token}`
          return api(original)
        } catch {
          localStorage.clear()
          window.location.href = '/auth'
        }
      }
    }
    return Promise.reject(err)
  }
)

export const WS_BASE = BASE.replace('https://', 'wss://').replace('http://', 'ws://')

// ── API helpers ───────────────────────────────────────────────────────────────
export const productsAPI = {
  list: (params) => api.get('/products', { params }),
  get:  (id)     => api.get(`/products/${id}`),
  events: (id)   => api.get(`/products/${id}/events`),
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
  track: (data) => api.post('/intent/track', data),
  score: (id)   => api.get(`/intent/score/${id}`),
}

export const ordersAPI = {
  checkout: (data) => api.post('/orders/checkout', data),
  list:     ()     => api.get('/orders'),
  get:      (id)   => api.get(`/orders/${id}`),
}
