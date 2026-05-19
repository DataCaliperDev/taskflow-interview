// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate, NavLink, useNavigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Tasks from './pages/Tasks'
import Users from './pages/Users'
import Profile from './pages/Profile'

function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">⚡ TaskFlow</div>

      <NavLink to="/" end className={({ isActive }) => 'sidebar-link' + (isActive ? ' active' : '')}>
        📋 Tasks
      </NavLink>
      <NavLink to="/users" className={({ isActive }) => 'sidebar-link' + (isActive ? ' active' : '')}>
        👥 Users
      </NavLink>

      <div className="sidebar-bottom">
        <NavLink to="/profile" className={({ isActive }) => 'sidebar-link' + (isActive ? ' active' : '')}>
          <span style={{ fontSize: 12 }}>👤 {user?.username}</span>
        </NavLink>
        <button className="sidebar-link btn" style={{ width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer', background: 'none', color: 'var(--muted)', fontWeight: 500 }}
          onClick={handleLogout}>
          🚪 Sign out
        </button>
      </div>
    </aside>
  )
}

function AppLayout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Tasks />} />
          <Route path="/users" element={<Users />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </main>
    </div>
  )
}

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', color: 'var(--muted)' }}>Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/*" element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          } />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
