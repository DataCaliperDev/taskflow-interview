// src/context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { usersApi, ApiAuthError } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      usersApi.me()
        .then(setUser)
        .catch((err) => {
          // Expired/invalid token => clear local auth and let RequireAuth
          // route guard redirect to /login within SPA.
          if (err instanceof ApiAuthError) {
            localStorage.removeItem('token')
            setUser(null)
            return
          }
          // For non-auth errors, keep the token and surface a clean logged-out
          // fallback to avoid broken app shell.
          setUser(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  function login(token) {
    localStorage.setItem('token', token)
    return usersApi.me().then(setUser)
  }

  function logout() {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
