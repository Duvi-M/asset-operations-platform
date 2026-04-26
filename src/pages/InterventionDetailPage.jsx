import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { StatusBadge, Loading, Empty, Alert } from '../components/ui'

const TYPE_LABELS = {
  installation:'Instalación', support:'Soporte', maintenance:'Mantenimiento',
  inspection:'Inspección', removal:'Retiro', other:'Otro'
}
function formatDate(d) {
  if (!d) return '—'
  const [y,m,day] = d.split('-')
  return `${day}/${m}/${y}`
}

// ── Associate Asset Panel ─────────────────────────────────────────────────────
function AssociatePanel({ interventionId, onAdded }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [notes, setNotes] = useState('')
  const [addingId, setAddingId] = useState(null)
  const [error, setError] = useState(null)

  async function doSearch() {
    if (!query.trim()) return

    setSearching(true)
    setResults([])
    setError(null)

    try {
      const res = await api.getAssets({ search: query.trim(), limit: 10 })
      setResults(res.items || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setSearching(false)
    }
  }

  async function addAsset(assetId) {
    setAddingId(assetId)
    setError(null)

    try {
      await api.addAssetToIntervention(interventionId, {
        asset_id: assetId,
        notes: notes || undefined,
      })

      setQuery('')
      setResults([])
      setNotes('')
      onAdded()
    } catch (e) {
      setError(e.message)
    } finally {
      setAddingId(null)
    }
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      <div className="flex gap-2">
        <input
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
          placeholder="Buscar por nombre, serial o QR: 9442, COMPUTER, SGOI-ASSET-94..."
        />

        <button className="btn btn-primary" disabled={searching} onClick={doSearch}>
          {searching ? 'Buscando…' : 'Buscar'}
        </button>
      </div>

      <div className="field">
        <label>Notas opcionales</label>
        <input
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Ej: instalado, revisado, reemplazado..."
        />
      </div>

      {error && <Alert type="error">{error}</Alert>}

      {results.length > 0 && (
        <div style={{
          display:'flex',
          flexDirection:'column',
          gap:6,
          maxHeight:300,
          overflowY:'auto',
          paddingRight:6,
          paddingBottom:8
        }}>
          {results.map(a => (
            <div
              key={a.id}
              style={{
                padding:'10px 12px',
                border:'1px solid var(--border)',
                borderRadius:'var(--radius)',
                background:'var(--bg-card)',
                display:'flex',
                alignItems:'center',
                justifyContent:'space-between',
                gap:12
              }}
            >
              <div>
                <div style={{ color:'var(--text-primary)', fontWeight:600 }}>
                  {a.item_name}
                </div>
                <div className="mono text-muted">
                  {a.serial_number || a.internal_code || a.qr_code_value}
                </div>
              </div>

              <div className="flex gap-2 items-center">
                <StatusBadge status={a.status} />
                <button
                  className="btn btn-sm btn-primary"
                  disabled={addingId === a.id}
                  onClick={() => addAsset(a.id)}
                >
                  {addingId === a.id ? 'Asociando…' : '+ Asociar'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Evidence Panel ────────────────────────────────────────────────────────────
function EvidencePanel({ interventionId, evidences, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  async function uploadFile(file) {
    if (!file) return
    const allowed = ['image/jpeg','image/jpg','image/png','image/webp','image/gif','image/bmp','image/tiff']
    if (!allowed.includes(file.type)) { setError('Solo se aceptan imágenes (JPG, PNG, WEBP, GIF...)'); return }
    setUploading(true); setError(null)
    try { await api.uploadEvidence(interventionId, file); onUploaded() }
    catch (e) { setError(e.message) }
    finally { setUploading(false) }
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      <div className={`upload-zone${dragging ? ' drag-over' : ''}`} style={{padding:'20px'}}
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); uploadFile(e.dataTransfer.files[0]) }}>
        {uploading
          ? <><div className="spinner" style={{margin:'0 auto 8px'}} /><p>Subiendo...</p></>
          : <><div className="upload-zone-icon" style={{fontSize:24}}>📷</div>
              <p><strong>Subir foto</strong> — arrastra o haz clic</p>
              <p style={{color:'var(--text-muted)',marginTop:4,fontSize:12}}>JPG · PNG · WEBP · GIF · máx. 10MB</p></>}
        <input ref={inputRef} type="file" accept="image/*" style={{display:'none'}}
          onChange={e => uploadFile(e.target.files[0])} />
      </div>
      {error && <Alert type="error">{error}</Alert>}
      {evidences.length > 0 ? (
        <div className="photo-grid">
          {evidences.map(ev => (
            <div key={ev.id} className="photo-thumb" title={ev.original_filename}>
              📷
            </div>
          ))}
        </div>
      ) : (
        <p className="text-muted" style={{fontSize:13,textAlign:'center',padding:'8px 0'}}>
          Sin evidencias todavía
        </p>
      )}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
// ── Main page ─────────────────────────────────────────────────────────────────
export default function InterventionDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [intervention, setIntervention] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setIntervention(await api.getIntervention(id))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [id])

  function downloadPdf() {
    const a = document.createElement('a')
    a.href = api.getPdfUrl(id)
    a.download = `intervencion_${id}.pdf`
    a.click()
  }

  if (loading) return <Loading label="Cargando intervención..." />
  if (error) return <Alert type="error">{error}</Alert>
  if (!intervention) return null

  const iv = intervention
  const typeLabel = TYPE_LABELS[iv.type] ?? iv.type

  return (
    <>
      {/* Header */}
      <div className="page-header">
        <h1 className="page-title">// INTERVENCIÓN #{iv.id}</h1>
        <span style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {typeLabel}
        </span>

        <button
          className="btn btn-ghost"
          style={{ marginLeft: 'auto' }}
          onClick={() => navigate('/interventions')}
        >
          ← Volver
        </button>

        <button className="btn btn-primary" onClick={downloadPdf}>
          ⬇ PDF
        </button>
      </div>

      {/* Info card */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">⬒ Datos Generales</span>
        </div>

        <div className="panel-body">
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))',
              gap: 16,
            }}
          >
            {[
              ['Tipo', typeLabel],
              ['RIG', iv.rig],
              ['Pozo', iv.pozo],
              ['Técnico', iv.technician],
              ['Fecha', formatDate(iv.date)],
              ['Equipos', iv.intervention_assets?.length ?? 0],
              ['Evidencias', iv.evidences?.length ?? 0],
            ].map(([l, v]) => (
              <div key={l}>
                <div
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: 'var(--text-muted)',
                    textTransform: 'uppercase',
                    letterSpacing: '.06em',
                    marginBottom: 4,
                  }}
                >
                  {l}
                </div>
                <div style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{v}</div>
              </div>
            ))}
          </div>

          {iv.description && (
            <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 10,
                  color: 'var(--text-muted)',
                  textTransform: 'uppercase',
                  letterSpacing: '.06em',
                  marginBottom: 6,
                }}
              >
                Descripción
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
                {iv.description}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Assets */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">
            ⬡ Equipos Asociados ({iv.intervention_assets?.length ?? 0})
          </span>
        </div>

        <div className="table-wrap">
          {!iv.intervention_assets?.length ? (
            <Empty icon="⬡" message="Sin equipos asociados aún" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Part Number</th>
                  <th>Serial / Código</th>
                  <th>Estado</th>
                  <th>Notas</th>
                </tr>
              </thead>

              <tbody>
                {iv.intervention_assets.map((ia) => (
                  <tr key={ia.id}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      {ia.asset?.item_name}
                    </td>
                    <td className="mono">{ia.asset?.part?.part_number ?? '—'}</td>
                    <td className="mono" style={{ color: 'var(--cyan)' }}>
                      {ia.asset?.serial_number || ia.asset?.internal_code || '—'}
                    </td>
                    <td>
                      <StatusBadge status={ia.asset?.status} />
                    </td>
                    <td className="text-muted" style={{ fontSize: 12 }}>
                      {ia.notes || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel-body" style={{ borderTop: '1px solid var(--border)' }}>
          <div
            style={{
              marginBottom: 12,
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              color: 'var(--amber)',
              textTransform: 'uppercase',
              letterSpacing: '.06em',
            }}
          >
            + Asociar equipo
          </div>

          <div
            style={{
              maxHeight: '420px',
              overflowY: 'auto',
              overflowX: 'hidden',
              paddingRight: 8,
              paddingBottom: 12,
            }}
          >
            <AssociatePanel interventionId={id} onAdded={load} />
          </div>
        </div>
      </div>

      {/* Evidence */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">📷 Evidencias ({iv.evidences?.length ?? 0})</span>
        </div>

        <div className="panel-body">
          <EvidencePanel
            interventionId={id}
            evidences={iv.evidences ?? []}
            onUploaded={load}
          />
        </div>
      </div>
    </>
  )
}
