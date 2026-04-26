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
  const [mode, setMode] = useState('search') // 'search' | 'scan'
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [scanCode, setScanCode] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [scanError, setScanError] = useState(null)
  const [notes, setNotes] = useState('')
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState(null)
  const [selected, setSelected] = useState(null)

  async function doSearch() {
    if (!query.trim()) return
    setSearching(true); setResults([])
    try {
      const res = await api.getAssets({ search: query.trim(), limit: 10 })
      setResults(res.items)
    } catch {}
    finally { setSearching(false) }
  }

  async function doScan(e) {
    e.preventDefault()
    if (!scanCode.trim()) return
    setScanResult(null); setScanError(null)
    try { setScanResult(await api.scanAsset(scanCode.trim())) }
    catch (e) { setScanError(e.message) }
  }

  async function addAsset(assetId) {
    setAdding(true); setAddError(null)
    try {
      await api.addAssetToIntervention(interventionId, { asset_id: assetId, notes: notes || undefined })
      setSelected(null); setScanResult(null); setScanCode(''); setQuery(''); setResults([])
      setNotes(''); onAdded()
    } catch (e) { setAddError(e.message) }
    finally { setAdding(false) }
  }

  const assetToAdd = selected || scanResult

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>
      {/* Mode toggle */}
      <div className="flex gap-2">
        <button className={`btn btn-sm ${mode==='search' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => { setMode('search'); setScanResult(null); setScanError(null) }}>
          ⌕ Buscar
        </button>
        <button className={`btn btn-sm ${mode==='scan' ? 'btn-primary' : 'btn-ghost'}`}
          onClick={() => { setMode('scan'); setResults([]); setSelected(null) }}>
          ⌖ Escanear QR
        </button>
      </div>

      {/* Search mode */}
      {mode === 'search' && (
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <div className="flex gap-2">
            <input value={query} onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doSearch()}
              placeholder="Nombre, serial, código interno..." />
            <button className="btn btn-ghost" disabled={searching} onClick={doSearch}>
              {searching ? '…' : '⌕'}
            </button>
          </div>
          {results.length > 0 && (
            <div style={{display:'flex',flexDirection:'column',gap:4}}>
              {results.map(a => (
                <div key={a.id} onClick={() => setSelected(a === selected ? null : a)}
                  style={{padding:'8px 12px',borderRadius:'var(--radius)',cursor:'pointer',
                    background: selected?.id === a.id ? 'var(--amber-glow)' : 'var(--bg-card)',
                    border: `1px solid ${selected?.id === a.id ? 'var(--amber)' : 'var(--border)'}`,
                    display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                  <div>
                    <span style={{fontWeight:500,color:'var(--text-primary)'}}>{a.item_name}</span>
                    <span className="mono text-muted" style={{marginLeft:10,fontSize:11}}>
                      {a.serial_number || a.internal_code}
                    </span>
                  </div>
                  <StatusBadge status={a.status} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Scan mode */}
      {mode === 'scan' && (
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <form onSubmit={doScan} className="flex gap-2">
            <input value={scanCode} onChange={e => setScanCode(e.target.value)}
              placeholder="SGOI-ASSET-42, SN-001..." />
            <button className="btn btn-ghost" type="submit">⌖ Scan</button>
          </form>
          {scanError && <Alert type="error">{scanError}</Alert>}
          {scanResult && (
            <div style={{padding:'8px 12px',background:'var(--amber-glow)',border:'1px solid var(--amber)',
              borderRadius:'var(--radius)',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
              <div>
                <span style={{fontWeight:500,color:'var(--text-primary)'}}>{scanResult.item_name}</span>
                <span className="mono text-muted" style={{marginLeft:10,fontSize:11}}>
                  {scanResult.serial_number || scanResult.internal_code}
                </span>
              </div>
              <StatusBadge status={scanResult.status} />
            </div>
          )}
        </div>
      )}

      {/* Add controls */}
      {assetToAdd && (
        <div style={{display:'flex',flexDirection:'column',gap:10,
          paddingTop:12,borderTop:'1px solid var(--border)'}}>
          <div className="field">
            <label>Notas (opcional)</label>
            <input value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Observaciones sobre este equipo en la intervención..." />
          </div>
          {addError && <Alert type="error">{addError}</Alert>}
          <button className="btn btn-primary" disabled={adding} onClick={() => addAsset(assetToAdd.id)}>
            {adding ? 'Asociando…' : `+ Asociar "${assetToAdd.item_name}"`}
          </button>
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
export default function InterventionDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [intervention, setIntervention] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  async function load() {
    setLoading(true); setError(null)
    try { setIntervention(await api.getIntervention(id)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [id])

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
        <span style={{color:'var(--cyan)',fontFamily:'var(--font-mono)',fontSize:13}}>{typeLabel}</span>
        <button className="btn btn-ghost" style={{marginLeft:'auto'}} onClick={() => navigate('/interventions')}>
          ← Volver
        </button>
        <button className="btn btn-primary" onClick={downloadPdf}>⬇ PDF</button>
      </div>

      {/* Info card */}
      <div className="panel">
        <div className="panel-header"><span className="panel-title">⬒ Datos Generales</span></div>
        <div className="panel-body">
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))',gap:16}}>
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
                <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--text-muted)',
                  textTransform:'uppercase',letterSpacing:'.06em',marginBottom:4}}>{l}</div>
                <div style={{color:'var(--text-primary)',fontWeight:500}}>{v}</div>
              </div>
            ))}
          </div>
          {iv.description && (
            <div style={{marginTop:16,paddingTop:16,borderTop:'1px solid var(--border)'}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--text-muted)',
                textTransform:'uppercase',letterSpacing:'.06em',marginBottom:6}}>Descripción</div>
              <p style={{color:'var(--text-secondary)',fontSize:13,lineHeight:1.6}}>{iv.description}</p>
            </div>
          )}
        </div>
      </div>

      {/* Assets */}
      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">⬡ Equipos Asociados ({iv.intervention_assets?.length ?? 0})</span>
        </div>
        <div className="table-wrap">
          {!iv.intervention_assets?.length ? (
            <Empty icon="⬡" message="Sin equipos asociados aún" />
          ) : (
            <table>
              <thead><tr>
                <th>Nombre</th><th>Part Number</th><th>Serial / Código</th><th>Estado</th><th>Notas</th>
              </tr></thead>
              <tbody>
                {iv.intervention_assets.map(ia => (
                  <tr key={ia.id}>
                    <td style={{color:'var(--text-primary)',fontWeight:500}}>{ia.asset?.item_name}</td>
                    <td className="mono">{ia.asset?.part?.part_number ?? '—'}</td>
                    <td className="mono" style={{color:'var(--cyan)'}}>
                      {ia.asset?.serial_number || ia.asset?.internal_code || '—'}
                    </td>
                    <td><StatusBadge status={ia.asset?.status} /></td>
                    <td className="text-muted" style={{fontSize:12}}>{ia.notes || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="panel-body" style={{borderTop:'1px solid var(--border)'}}>
          <div style={{marginBottom:10,fontFamily:'var(--font-mono)',fontSize:11,
            color:'var(--amber)',textTransform:'uppercase',letterSpacing:'.06em'}}>
            + Asociar equipo
          </div>
          <AssociatePanel interventionId={id} onAdded={load} />
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
