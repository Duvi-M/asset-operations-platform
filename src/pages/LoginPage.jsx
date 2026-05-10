import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Alert } from '../components/ui'
import { useAuth } from '../auth/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (user) {
    const destination = location.state?.from?.pathname || '/assets'
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await login(email, password)
      const destination = location.state?.from?.pathname || '/assets'
      navigate(destination, { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">AssetOps</div>
        <h1 className="auth-title">Iniciar sesión</h1>
        <p className="auth-copy">
          Accede para gestionar equipos, intervenciones, evidencias y reportes desde campo.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          {error && <Alert type="error">{error}</Alert>}

          <div className="field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="tecnico@empresa.com"
              autoComplete="email"
              autoFocus
              required
            />
          </div>

          <div className="field">
            <label>Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
              required
            />
          </div>

          <button className="btn btn-primary auth-submit" disabled={loading}>
            {loading ? 'Ingresando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
