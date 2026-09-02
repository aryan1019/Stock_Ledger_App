import axios from 'axios'

const BASE = import.meta.env.VITE_API_BASE || '/api/v1'

export const ACCESS_KEY = 'ledger.access'
export const REFRESH_KEY = 'ledger.refresh'

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set(access, refresh) {
    if (access) localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const api = axios.create({ baseURL: BASE, headers: { 'Content-Type': 'application/json' } })

api.interceptors.request.use((config) => {
  const token = tokens.access()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Single-flight refresh: many parallel 401s share one refresh round-trip.
let refreshing = null

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config
    const status = error.response?.status
    const isAuthCall = original?.url?.includes('/auth/')

    if (status !== 401 || original?._retried || isAuthCall) {
      return Promise.reject(error)
    }
    const refresh = tokens.refresh()
    if (!refresh) {
      tokens.clear()
      return Promise.reject(error)
    }

    original._retried = true
    refreshing =
      refreshing ||
      axios
        .post(`${BASE}/auth/refresh/`, { refresh })
        .then(({ data }) => {
          tokens.set(data.access, data.refresh)
          return data.access
        })
        .catch((e) => {
          tokens.clear()
          throw e
        })
        .finally(() => {
          refreshing = null
        })

    try {
      const access = await refreshing
      original.headers.Authorization = `Bearer ${access}`
      return api(original)
    } catch (e) {
      return Promise.reject(e)
    }
  },
)

/** Flattens DRF error bodies into one readable sentence. */
export function apiError(error, fallback = 'Something went wrong.') {
  const data = error?.response?.data
  if (!data) return error?.message || fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const first = Object.entries(data)[0]
  if (!first) return fallback
  const [field, messages] = first
  const text = Array.isArray(messages) ? messages[0] : String(messages)
  return field === 'non_field_errors' ? text : `${field}: ${text}`
}

export default api
