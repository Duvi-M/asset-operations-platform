// ── StatusBadge ───────────────────────────────────────────────────────────────
const STATUS_LABELS = {
  available:   'Disponible',
  in_use:      'En Uso',
  maintenance: 'Mantenimiento',
  retired:     'Retirado',
  unknown:     'Desconocido',
}

export function StatusBadge({ status }) {
  return (
    <span className={`badge badge-${status}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

// ── Spinner ───────────────────────────────────────────────────────────────────
export function Spinner({ size = 20 }) {
  return (
    <div
      className="spinner"
      style={{ width: size, height: size }}
    />
  )
}

// ── Loading block ─────────────────────────────────────────────────────────────
export function Loading({ label = 'Cargando...' }) {
  return (
    <div className="flex items-center gap-3" style={{ padding: '32px 0', justifyContent: 'center' }}>
      <Spinner />
      <span className="text-muted">{label}</span>
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function Empty({ icon = '⬡', message = 'Sin datos' }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">{icon}</div>
      <p>{message}</p>
    </div>
  )
}

// ── Alert ─────────────────────────────────────────────────────────────────────
export function Alert({ type = 'info', children }) {
  return <div className={`alert alert-${type}`}>{children}</div>
}

// ── Pagination ────────────────────────────────────────────────────────────────
export function Pagination({ skip, limit, total, onSkip }) {
  const page = Math.floor(skip / limit) + 1
  const totalPages = Math.ceil(total / limit)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center gap-3 justify-between" style={{ marginTop: 14 }}>
      <span className="text-muted text-mono">
        {skip + 1}–{Math.min(skip + limit, total)} de {total}
      </span>
      <div className="flex gap-2">
        <button
          className="btn btn-ghost btn-sm"
          disabled={skip === 0}
          onClick={() => onSkip(Math.max(0, skip - limit))}
        >
          ← Anterior
        </button>
        <span className="text-muted text-mono" style={{ padding: '5px 8px' }}>
          {page}/{totalPages}
        </span>
        <button
          className="btn btn-ghost btn-sm"
          disabled={skip + limit >= total}
          onClick={() => onSkip(skip + limit)}
        >
          Siguiente →
        </button>
      </div>
    </div>
  )
}
