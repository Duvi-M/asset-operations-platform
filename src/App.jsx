import { Routes, Route, NavLink, useNavigate, useLocation } from 'react-router-dom'
import AssetsPage from './pages/AssetsPage'
import ImportPage from './pages/ImportPage'
import InterventionsPage from './pages/InterventionsPage'
import InterventionDetailPage from './pages/InterventionDetailPage'
import NewInterventionPage from './pages/NewInterventionPage'

const NAV = [
  {
    section: 'Inventario',
    items: [
      { to: '/assets', icon: '⬡', label: 'Assets' },
      { to: '/import', icon: '⬆', label: 'Importar Excel' },
    ],
  },
  {
    section: 'Operaciones',
    items: [
      { to: '/interventions', icon: '⬒', label: 'Intervenciones' },
      { to: '/interventions/new', icon: '+', label: 'Nueva Intervención' },
    ],
  },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="app-shell">
      {/* Header */}
      <header className="header">
        <span className="header-logo">SGOI</span>
        <span className="header-sub">Sistema de Gestión Operativa e Inventario</span>
        <span className="header-dot" title="API conectada" />
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        {NAV.map(({ section, items }) => (
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
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="nav-link"
          >
            <span className="nav-icon">⎇</span>
            API Docs
          </a>
        </div>
      </nav>

      {/* Main */}
      <main className="main">
        <Routes>
          <Route path="/" element={<AssetsPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/interventions" element={<InterventionsPage />} />
          <Route path="/interventions/new" element={<NewInterventionPage />} />
          <Route path="/interventions/:id" element={<InterventionDetailPage />} />
        </Routes>
      </main>
    </div>
  )
}
