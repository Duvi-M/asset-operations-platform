import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { api } from '../services/api'
import { StatusBadge, Loading, Empty, Alert } from '../components/ui'
import { DocsBridgePanel } from '../components/DocsBridge'

const TYPE_LABELS = {
  installation: 'Instalación', support: 'Soporte', maintenance: 'Mantenimiento',
  inspection: 'Inspección', removal: 'Retiro', other: 'Otro'
}

function formatDate(d) {
  if (!d) return '—'
  const [y, m, day] = d.split('-')
  return `${day}/${m}/${y}`
}

function AssociatePanel({ interventionId, onAdded }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [notes, setNotes] = useState('')
  const [addingId, setAddingId] = useState(null)
  const [error, setError] = useState(null)
  const [locationNote, setLocationNote] = useState('')
  const [success, setSuccess] = useState(null)

  async function doSearch() {
    if (!query.trim()) return
    setSearching(true)
    setResults([])
    setError(null)
    setSuccess(null)

    try {
      const res = await api.getAssets({ search: query.trim(), limit: 10 })
      setResults(res.items || [])
      if ((res.items || []).length === 0) {
        setError('No se encontraron equipos con ese dato. Prueba con serial, código interno o valor QR.')
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setSearching(false)
    }
  }

  async function addAsset(assetId) {
    setAddingId(assetId)
    setError(null)
    setSuccess(null)

    try {
      const asset = results.find(item => item.id === assetId)
      await api.addAssetToIntervention(interventionId, {
        asset_id: assetId,
        location_note: locationNote || null,
        notes: notes || null,
      })

      setQuery('')
      setResults([])
      setLocationNote('')
      setNotes('')
      setSuccess(`Equipo ${asset?.item_name || `#${assetId}`} asociado correctamente.`)
      onAdded()
    } catch (e) {
      setError(e.message)
    } finally {
      setAddingId(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="flex gap-2">
        <input
          className="touch-input"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && doSearch()}
          enterKeyHint="search"
          placeholder="Buscar por nombre, serial o QR: 9442, COMPUTER, SGOI-ASSET-94..."
        />

        <button className="btn btn-primary" disabled={searching} onClick={doSearch}>
          {searching ? 'Buscando…' : 'Buscar'}
        </button>
      </div>

      <div className="quick-hint-row">
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setQuery('SGOI-ASSET-')}>
          Pegar prefijo QR
        </button>
        <span className="helper-text">Primero busca y luego completa ubicación o notas solo si agregan contexto real.</span>
      </div>

      <div className="field">
        <label>Ubicación en pozo / área</label>
        <input
          className="touch-input"
          value={locationNote}
          onChange={e => setLocationNote(e.target.value)}
          placeholder="Ej: Cabina del operador, Rack DAQ, Cabezal del pozo..."
        />
      </div>

      <div className="field">
        <label>Notas opcionales</label>
        <input
          className="touch-input"
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Ej: cable dañado, pendiente revisión, reemplazado..."
        />
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {results.length > 0 && (
        <div className="associate-results">
          {results.map(a => (
            <div key={a.id} className="associate-result-card">
              <div className="associate-result-main">
                <div style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                  {a.item_name}
                </div>
                <div className="mono text-muted">
                  {a.serial_number || a.internal_code || a.qr_code_value}
                </div>
              </div>

              <div className="associate-result-meta">
                <StatusBadge status={a.status} />
                <button
                  className="btn btn-primary"
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

function EvidencePanel({ interventionId, evidences, onUploaded }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [previewUrl, setPreviewUrl] = useState(null)
  const [previewName, setPreviewName] = useState('')
  const inputRef = useRef()

  async function uploadFile(file) {
    if (!file) return

    const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif', 'image/bmp', 'image/tiff']
    if (!allowed.includes(file.type)) {
      setError('Solo se aceptan imágenes (JPG, PNG, WEBP, GIF...)')
      return
    }

    const localPreview = URL.createObjectURL(file)
    setUploading(true)
    setError(null)
    setSuccess(null)
    setPreviewUrl(localPreview)
    setPreviewName(file.name)

    try {
      await api.uploadEvidence(interventionId, file)
      setSuccess(`Imagen ${file.name} subida correctamente.`)
      onUploaded()
    } catch (e) {
      setError(e.message)
      URL.revokeObjectURL(localPreview)
      setPreviewUrl(null)
      setPreviewName('')
    } finally {
      setUploading(false)
    }
  }

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
  }, [previewUrl])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        className={`upload-zone touch-zone${dragging ? ' drag-over' : ''}`}
        style={{ padding: '20px' }}
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); uploadFile(e.dataTransfer.files[0]) }}
      >
        {uploading
          ? <><div className="spinner" style={{ margin: '0 auto 8px' }} /><p>Subiendo...</p></>
          : <><div className="upload-zone-icon" style={{ fontSize: 24 }}>📷</div>
              <p><strong>Tomar foto o subir imagen</strong></p>
              <p className="upload-hint upload-hint-strong">En móvil se abrirá primero la cámara trasera cuando el navegador lo permita.</p>
              <p className="upload-hint">JPG · PNG · WEBP · GIF · máx. 10MB</p></>}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          capture="environment"
          style={{ display: 'none' }}
          onChange={e => uploadFile(e.target.files[0])}
        />
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {previewUrl && (
        <div className="evidence-preview-card">
          <div className="evidence-preview-header">
            <span className="panel-title">Vista previa inmediata</span>
            <span className="helper-text">{uploading ? 'Subiendo…' : 'Lista'}</span>
          </div>
          <div className="evidence-preview-image">
            <img src={previewUrl} alt={previewName || 'Vista previa de evidencia'} />
          </div>
          <div className="photo-caption">{previewName}</div>
        </div>
      )}

      {evidences.length > 0 ? (
        <div className="photo-grid">
          {evidences.map(ev => (
            <div key={ev.id}>
              <div className="photo-thumb" title={ev.original_filename}>
                {ev.file_path?.startsWith('http') ? (
                  <img src={ev.file_path} alt={ev.original_filename || `Evidencia ${ev.id}`} loading="lazy" />
                ) : (
                  '📷'
                )}
              </div>
              <div className="photo-caption">
                {ev.original_filename || `Evidencia ${ev.id}`}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-muted" style={{ fontSize: 13, textAlign: 'center', padding: '8px 0' }}>
          Sin evidencias todavía
        </p>
      )}
    </div>
  )
}

export default function InterventionDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [intervention, setIntervention] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [flash, setFlash] = useState(location.state?.flash || null)
  const [editingDescription, setEditingDescription] = useState(false)
  const [descriptionDraft, setDescriptionDraft] = useState('')
  const [savingDescription, setSavingDescription] = useState(false)

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

  useEffect(() => {
    if (!flash) return undefined
    const timer = window.setTimeout(() => setFlash(null), 4000)
    return () => window.clearTimeout(timer)
  }, [flash])

  async function saveDescription() {
    setSavingDescription(true)
    setError(null)
    setFlash(null)

    try {
      await api.updateIntervention(id, {
        description: descriptionDraft,
      })

      setEditingDescription(false)
      setFlash({ type: 'success', message: 'Descripción actualizada.' })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSavingDescription(false)
    }
  }

  async function downloadPdf() {
    try {
      await api.downloadPdf(id)
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return <Loading label="Cargando intervención..." />
  if (error) return <Alert type="error">{error}</Alert>
  if (!intervention) return null

  const iv = intervention
  const typeLabel = TYPE_LABELS[iv.type] ?? iv.type

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// INTERVENCIÓN #{iv.id}</h1>
        <span style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          {typeLabel}
        </span>

        <div className="mobile-actions" style={{ marginLeft: 'auto', justifyContent: 'flex-end' }}>
          <button
            className="btn btn-ghost"
            onClick={() => navigate('/interventions')}
          >
            ← Volver
          </button>

          <button className="btn btn-primary" onClick={downloadPdf}>
            ⬇ Descargar PDF
          </button>
        </div>
      </div>

      {flash && <Alert type={flash.type || 'success'}>{flash.message}</Alert>}
      {error && <Alert type="error">{error}</Alert>}

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">⬒ Datos Generales</span>
        </div>

        <div className="panel-body">
          <div className="detail-grid">
            {[
              ['Tipo', typeLabel],
              ['RIG', iv.rig],
              ['Pozo', iv.pozo],
              ['Técnico', iv.technician],
              ['Fecha', formatDate(iv.date)],
              ['Fecha finalización', formatDate(iv.end_date)],
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

          <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
            <div
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '.06em',
                marginBottom: 6,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>Descripción</span>

              {!editingDescription && (
                <button
                  className="btn btn-sm btn-ghost"
                  onClick={() => {
                    setDescriptionDraft(iv.description || '')
                    setEditingDescription(true)
                  }}
                >
                  Editar
                </button>
              )}
            </div>

            {editingDescription ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <textarea
                  value={descriptionDraft}
                  onChange={e => setDescriptionDraft(e.target.value)}
                  rows={4}
                  placeholder="Detalle de la intervención..."
                />

                <div className="mobile-actions">
                  <button
                    className="btn btn-primary"
                    disabled={savingDescription}
                    onClick={saveDescription}
                  >
                    {savingDescription ? 'Guardando…' : 'Guardar descripción'}
                  </button>

                  <button
                    className="btn btn-ghost"
                    disabled={savingDescription}
                    onClick={() => setEditingDescription(false)}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-secondary)', fontSize: 13, lineHeight: 1.6 }}>
                {iv.description || 'Sin descripción registrada.'}
              </p>
            )}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">
            ⬡ Equipos Asociados ({iv.intervention_assets?.length ?? 0})
          </span>
          <span className="helper-text">Asocia primero el equipo principal para completar el reporte más rápido.</span>
        </div>

        <div className="table-wrap">
          {!iv.intervention_assets?.length ? (
            <Empty icon="⬡" message="Sin equipos asociados aún" />
          ) : (
            <table className="responsive-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Part Number</th>
                  <th>Serial / Código</th>
                  <th>Estado</th>
                  <th>Ubicación en pozo / área</th>
                  <th>Notas</th>
                </tr>
              </thead>

              <tbody>
                {iv.intervention_assets.map((ia) => (
                  <tr key={ia.id}>
                    <td data-label="Nombre" style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                      {ia.asset?.item_name}
                    </td>
                    <td data-label="Part Number" className="mono">{ia.asset?.part?.part_number ?? '—'}</td>
                    <td data-label="Serial / Código" className="mono" style={{ color: 'var(--cyan)' }}>
                      {ia.asset?.serial_number || ia.asset?.internal_code || '—'}
                    </td>
                    <td data-label="Estado">
                      <StatusBadge status={ia.asset?.status} />
                    </td>
                    <td data-label="Ubicación" className="text-muted" style={{ fontSize: 12 }}>
                      {ia.location_note || ia.asset?.location || '—'}
                    </td>
                    <td data-label="Notas" className="text-muted" style={{ fontSize: 12 }}>
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

          <div className="associate-scroll" style={{ maxHeight: '420px', paddingBottom: 12 }}>
            <AssociatePanel interventionId={id} onAdded={load} />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▧ Docs for Associated Assets</span>
          <span className="helper-text">Quick checks against the external SGOI Docs portal.</span>
        </div>

        <div className="panel-body">
          {!iv.intervention_assets?.length ? (
            <Empty icon="▧" message="Associate assets to check technical documentation" />
          ) : (
            <div className="intervention-packet-list">
              {iv.intervention_assets.map((ia) => (
                <DocsBridgePanel
                  key={ia.id}
                  asset={ia.asset}
                  title={ia.asset?.item_name || `Asset #${ia.asset_id}`}
                  compact
                  limit={12}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">📷 Evidencias ({iv.evidences?.length ?? 0})</span>
          <span className="helper-text">Toma la foto en el momento para que quede adjunta al reporte.</span>
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
