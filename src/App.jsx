import { Routes, Route, NavLink, useLocation, Navigate, Outlet } from 'react-router-dom'
import AssetsPage from './pages/AssetsPage'
import ImportPage from './pages/ImportPage'
import InterventionsPage from './pages/InterventionsPage'
import InterventionDetailPage from './pages/InterventionDetailPage'
import NewInterventionPage from './pages/NewInterventionPage'
import WorkOrdersPage from './pages/WorkOrdersPage'
import WorkOrderDetailPage from './pages/WorkOrderDetailPage'
import DocsPortalPage from './pages/DocsPortalPage'
import LoginPage from './pages/LoginPage'
import { Loading } from './components/ui'
import { api } from './services/api'
import { useAuth } from './auth/AuthContext'

const NAV = [
  {
    section: 'Inventario',
    items: [
      { to: '/assets', icon: '⬡', label: 'Assets', roles: ['admin', 'technician'] },
      { to: '/import', icon: '⬆', label: 'Importar Excel', roles: ['admin'] },
    ],
  },
  {
    section: 'Operaciones',
    items: [
      { to: '/interventions', icon: '⬒', label: 'Intervenciones', roles: ['admin', 'technician'] },
      { to: '/interventions/new', icon: '+', label: 'Nueva Intervención', roles: ['admin', 'technician'] },
      { to: '/work-orders', icon: '▣', label: 'Work Orders', roles: ['admin', 'technician'] },
    ],
  },
  {
    section: 'Conocimiento',
    items: [
      { to: '/docs-portal', icon: '▧', label: 'SGOI Docs', roles: ['admin', 'technician'] },
    ],
  },
]

function RequireAuth() {
  const { user, booting } = useAuth()
  const location = useLocation()

  if (booting) return <Loading label="Restaurando sesión..." />
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}

function RequireRole({ allowedRoles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (!allowedRoles.includes(user.role)) return <Navigate to="/assets" replace />
  return children
}

function AppShell() {
  const location = useLocation()
  const { user, logout } = useAuth()
  const nav = NAV.map(section => ({
    ...section,
    items: section.items.filter(item => item.roles.includes(user.role)),
  }))

  return (
    <div className="app-shell">
      <header className="header">
        <span className="header-logo">SGOI</span>
        <span className="header-sub">Sistema de Gestión Operativa e Inventario</span>
        <div className="header-user">
          <div className="header-user-meta">
            <span className="header-user-name">{user.full_name}</span>
            <span className="header-user-role">{user.role === 'admin' ? 'Admin' : 'Técnico'}</span>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={logout}>
            Salir
          </button>
        </div>
        <span className="header-dot" title="API conectada" />
      </header>

      <nav className="sidebar">
        {nav.map(({ section, items }) => (
          <div className="nav-section" key={section}>
            <span className="nav-label">{section}</span>
            {items.map(({ to, icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  'nav-link' + (isActive || location.pathname === to ? ' active' : '')
                }
                end={to === '/interventions'}
              >
                <span className="nav-icon">{icon}</span>
                {label}
              </NavLink>
            ))}
            <div className="nav-divider" />
          </div>
        ))}

        <div className="nav-section">
          <span className="nav-label">Sistema</span>
          <a
            href={api.docsUrl}
            target="_blank"
            rel="noreferrer"
            className="nav-link"
          >
            <span className="nav-icon">⎇</span>
            API Docs
          </a>
        </div>
      </nav>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/assets" replace />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route
            path="/import"
            element={(
              <RequireRole allowedRoles={['admin']}>
                <ImportPage />
              </RequireRole>
            )}
          />
          <Route path="/interventions" element={<InterventionsPage />} />
          <Route path="/interventions/new" element={<NewInterventionPage />} />
          <Route path="/interventions/:id" element={<InterventionDetailPage />} />
          <Route path="/work-orders" element={<WorkOrdersPage />} />
          <Route path="/work-orders/:id" element={<WorkOrderDetailPage />} />
          <Route path="/docs-portal" element={<DocsPortalPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
