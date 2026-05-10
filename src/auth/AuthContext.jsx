import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'

const AuthContext = createContext(null)

function loadStoredSession() {
  try {
    const raw = window.localStorage.getItem(api.storageKey)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persistSession(session) {
  if (!session) {
    window.localStorage.removeItem(api.storageKey)
    return
  }
  window.localStorage.setItem(api.storageKey, JSON.stringify(session))
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(() => loadStoredSession())
  const [booting, setBooting] = useState(true)

  useEffect(() => {
    let alive = true

    async function bootstrap() {
      const stored = loadStoredSession()
      if (!stored?.token) {
        if (alive) {
          setSession(null)
          setBooting(false)
        }
        return
      }

      try {
        const user = await api.getMe()
        if (!alive) return
        const nextSession = { token: stored.token, user }
        setSession(nextSession)
        persistSession(nextSession)
      } catch {
        if (!alive) return
        setSession(null)
        persistSession(null)
      } finally {
        if (alive) setBooting(false)
      }
    }

    bootstrap()

    function handleForcedLogout() {
      setSession(null)
      persistSession(null)
    }

    window.addEventListener('auth:logout', handleForcedLogout)
    return () => {
      alive = false
      window.removeEventListener('auth:logout', handleForcedLogout)
    }
  }, [])

  async function login(email, password) {
    const result = await api.login(email, password)
    const nextSession = {
      token: result.access_token,
      user: result.user,
    }
    setSession(nextSession)
    persistSession(nextSession)
    return result.user
  }

  function logout() {
    setSession(null)
    persistSession(null)
  }

  const value = useMemo(() => ({
    token: session?.token || null,
    user: session?.user || null,
    booting,
    login,
    logout,
    isAdmin: session?.user?.role === 'admin',
    isTechnician: session?.user?.role === 'technician',
  }), [session, booting])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
