import { NavLink } from 'react-router-dom'

const links = [
  { to: '/assets',        icon: '⬡', label: 'Inventario' },
  { to: '/import',        icon: '⇪', label: 'Importar Excel' },
  { to: '/interventions', icon: '≡', label: 'Intervenciones' },
  { to: '/interventions/new', icon: '+', label: 'Nueva Intervención' },
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="wordmark">SGOI</div>
        <div className="tagline">Gestión Operativa e Inventario</div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Inventario</div>
        <NavLink to="/assets" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">⬡</span> Equipos / Assets
        </NavLink>
        <NavLink to="/import" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">↑</span> Importar Excel
        </NavLink>

        <div className="nav-section-label" style={{ marginTop: 12 }}>Operaciones</div>
        <NavLink to="/interventions" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">≡</span> Intervenciones
        </NavLink>
        <NavLink to="/interventions/new" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">＋</span> Nueva Intervención
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        v0.1.0-mvp<br />
        Oil &amp; Gas Field Ops
      </div>
    </aside>
  )
}
