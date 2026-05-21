// src/pages/Register.jsx
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '../api/client'
import { useAuth } from '../context/AuthContext'

/**
 * Parse an API error into a list of human-readable strings.
 *
 * - Pydantic 422: detail is an array of objects → extract each `msg`,
 *   stripping the "Value error, " prefix that Pydantic v2 prepends.
 * - Any other error (400, 500, …): detail is a plain string → wrap in array.
 */
function parseErrors(errMessage) {
  try {
    const parsed = JSON.parse(errMessage)
    if (Array.isArray(parsed)) {
      return parsed.map(e =>
        (e.msg || String(e)).replace(/^Value error,\s*/i, '')
      )
    }
  } catch {
    // not JSON — fall through
  }
  return [errMessage]
}

export default function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ username: '', email: '', password: '' })
  const [errors, setErrors] = useState([])
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setErrors([])
    setLoading(true)
    try {
      await authApi.register(form)
      const data = await authApi.login(form.username, form.password)
      await login(data.access_token)
      navigate('/')
    } catch (err) {
      setErrors(parseErrors(err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-title">Create account</div>
        <div className="auth-sub">Get started with TaskFlow</div>

        {errors.length > 0 && (
          <div className="alert alert-error">
            {errors.length === 1
              ? errors[0]
              : <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {errors.map((msg, i) => <li key={i}>{msg}</li>)}
                </ul>
            }
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Username</label>
            <input className="form-control" placeholder="Choose a username"
              value={form.username} onChange={e => setForm({ ...form, username: e.target.value })} required />
          </div>
          <div className="form-group">
            <label className="form-label">Email</label>
            <input className="form-control" type="email" placeholder="you@example.com"
              value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input className="form-control" type="password" placeholder="Min. 8 characters"
              value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required />
          </div>
          <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
            {loading ? <span className="spinner" /> : 'Create account'}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  )
}
