// src/api/client.js
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'
// In dev, Vite proxies /api/* -> http://localhost:8000/*
// This prevents collisions with frontend SPA routes like /users.

function getToken() {
  return localStorage.getItem('token')
}

export class ApiAuthError extends Error {
  constructor(message = 'Unauthorized') {
    super(message)
    this.name = 'ApiAuthError'
  }
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers })

  if (res.status === 401) {
    // Do not hard-redirect here. Let React auth state + route guards handle
    // navigation, otherwise we get full-page jumps and brittle UX.
    localStorage.removeItem('token')
    throw new ApiAuthError('Unauthorized')
  }

  const data = res.headers.get('content-type')?.includes('application/json')
    ? await res.json()
    : null

  if (!res.ok) {
    const msg = data?.detail || `Request failed: ${res.status}`
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg))
  }

  return data
}

// ── Auth ─────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (username, password) => {
    const body = new URLSearchParams({ username, password })
    return fetch(`${BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    }).then(async res => {
      const isJson = res.headers.get('content-type')?.includes('application/json')
      let data = null
      if (isJson) {
        data = await res.json()
      } else {
        // Avoid "Unexpected token ..." when backend returns plain-text 500.
        const text = await res.text()
        data = text ? { detail: text } : null
      }
      if (!res.ok) throw new Error(data?.detail || 'Login failed')
      return data
    })
  },
  register: (payload) => request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
}

// ── Tasks ─────────────────────────────────────────────────────────────────────
export const tasksApi = {
  list: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null)).toString()
    return request(`/tasks/${qs ? '?' + qs : ''}`)
  },
  search: (q) => request(`/tasks/search?q=${encodeURIComponent(q)}`),
  get: (id) => request(`/tasks/${id}`),
  create: (payload) => request('/tasks/', { method: 'POST', body: JSON.stringify(payload) }),
  update: (id, payload) => request(`/tasks/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  delete: (id) => request(`/tasks/${id}`, { method: 'DELETE' }),
  addComment: (taskId, content) =>
    request(`/tasks/${taskId}/comments`, { method: 'POST', body: JSON.stringify({ content }) }),
  summary: () => request('/tasks/summary/by-user'),
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersApi = {
  list: () => request('/users/'),
  me: () => request('/users/me'),
  get: (id) => request(`/users/${id}`),
  update: (id, payload) => request(`/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  delete: (id) => request(`/users/${id}`, { method: 'DELETE' }),
  tasks: (id) => request(`/users/${id}/tasks`),
}
