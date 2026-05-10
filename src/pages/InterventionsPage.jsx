import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { Loading, Empty, Pagination } from '../components/ui'

const TYPE_LABELS = {
  installation:'Instalación', support:'Soporte', maintenance:'Mantenimiento',
  inspection:'Inspección', removal:'Retiro', other:'Otro'
}
const TYPE_COLORS = {
  installation:'var(--green)', support:'var(--blue)', maintenance:'var(--amber)',
  inspection:'var(--cyan)', removal:'var(--red)', other:'var(--text-muted)'
}

function formatDate(d) {
  if (!d) return '—'
  const [y,m,day] = d.split('-')
  return `${day}/${m}/${y}`
}

export default function InterventionsPage() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const LIMIT = 50

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await api.getInterventions({ skip, limit: LIMIT })
      setItems(res.items); setTotal(res.total)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [skip])

  useEffect(() => { load() }, [load])

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// INTERVENCIONES</h1>
        {!loading && <span className="page-count">{total} reportes</span>}
        <button className="btn btn-primary" style={{marginLeft:'auto'}} onClick={() => navigate('/interventions/new')}>
          + Nueva intervención
        </button>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▤ Reportes de Intervención</span>
          <button className="btn btn-ghost btn-sm" onClick={load}>↺</button>
        </div>
        {error && <div className="alert alert-error" style={{margin:16}}>{error}</div>}
        <div className="table-wrap">
          {loading ? <Loading /> : items.length === 0 ? (
            <Empty icon="⬒" message="No hay intervenciones. Crea una nueva." />
          ) : (
            <table className="responsive-table">
              <thead><tr>
                <th>ID</th><th>Tipo</th><th>RIG</th><th>Pozo</th>
                <th>Técnico</th><th>Fecha</th><th>Equipos</th><th>Fotos</th><th></th>
              </tr></thead>
              <tbody>
                {items.map(i => (
                  <tr key={i.id} style={{cursor:'pointer'}} onClick={() => navigate(`/interventions/${i.id}`)}>
                    <td data-label="ID" className="mono text-muted">{i.id}</td>
                    <td data-label="Tipo">
                      <span className="mono" style={{color: TYPE_COLORS[i.type] ?? 'var(--text-muted)', fontSize:11}}>
                        {TYPE_LABELS[i.type] ?? i.type}
                      </span>
                    </td>
                    <td data-label="RIG" style={{fontWeight:500,color:'var(--text-primary)'}}>{i.rig}</td>
                    <td data-label="Pozo" className="mono" style={{color:'var(--cyan)'}}>{i.pozo}</td>
                    <td data-label="Técnico">{i.technician}</td>
                    <td data-label="Fecha" className="mono text-muted">{formatDate(i.date)}</td>
                    <td data-label="Equipos" className="mono" style={{color: i.asset_count > 0 ? 'var(--blue)' : 'var(--text-muted)'}}>
                      {i.asset_count}
                    </td>
                    <td data-label="Fotos" className="mono" style={{color: i.evidence_count > 0 ? 'var(--green)' : 'var(--text-muted)'}}>
                      {i.evidence_count}
                    </td>
                    <td data-label="Abrir"><span style={{color:'var(--amber)',fontSize:13}}>→</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {!loading && <div style={{padding:'0 18px 14px'}}>
          <Pagination skip={skip} limit={LIMIT} total={total} onSkip={setSkip} />
        </div>}
      </div>
    </>
  )
}
