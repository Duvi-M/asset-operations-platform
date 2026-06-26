import { useState, useEffect, useCallback, useRef } from 'react'
import jsQR from 'jsqr'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import { StatusBadge, Loading, Empty, Pagination } from '../components/ui'
import { DocsBridgePanel, docsPortalPathForAsset } from '../components/DocsBridge'

function getCameraErrorMessage(error) {
  if (!error) return 'No se pudo abrir la cámara.'

  switch (error.name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return 'Permiso de cámara denegado. Habilita la cámara en el navegador y vuelve a intentarlo.'
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'No se encontró una cámara disponible en este dispositivo.'
    case 'NotReadableError':
    case 'TrackStartError':
      return 'La cámara está siendo usada por otra aplicación. Cierra la otra app y reintenta.'
    case 'OverconstrainedError':
    case 'ConstraintNotSatisfiedError':
      return 'No fue posible usar la cámara trasera. Prueba nuevamente o usa la búsqueda manual.'
    case 'SecurityError':
      return 'La cámara solo funciona sobre HTTPS o localhost. Abre la app desde una URL segura.'
    default:
      return error.message || 'No se pudo abrir la cámara.'
  }
}

function ScannerModal({ open, onClose, onDetect }) {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const rafRef = useRef(null)
  const detectedRef = useRef(false)
  const [cameraError, setCameraError] = useState(null)
  const [starting, setStarting] = useState(false)

  useEffect(() => {
    if (!open) return undefined

    let cancelled = false
    detectedRef.current = false

    async function startScanner() {
      setStarting(true)
      setCameraError(null)

      try {
        if (!navigator.mediaDevices?.getUserMedia) {
          throw new Error('Este navegador no soporta acceso a cámara.')
        }

        const preferred = {
          video: {
            facingMode: { ideal: 'environment' },
          },
          audio: false,
        }

        let stream
        try {
          stream = await navigator.mediaDevices.getUserMedia(preferred)
        } catch (error) {
          stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
        }

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        streamRef.current = stream
        const video = videoRef.current
        if (!video) return

        video.srcObject = stream
        video.setAttribute('playsinline', 'true')
        await video.play()

        const tick = () => {
          if (cancelled || detectedRef.current) return

          const canvas = canvasRef.current
          const currentVideo = videoRef.current
          if (!canvas || !currentVideo) {
            rafRef.current = requestAnimationFrame(tick)
            return
          }

          if (currentVideo.readyState === currentVideo.HAVE_ENOUGH_DATA) {
            const width = currentVideo.videoWidth
            const height = currentVideo.videoHeight
            canvas.width = width
            canvas.height = height

            const ctx = canvas.getContext('2d', { willReadFrequently: true })
            if (ctx) {
              ctx.drawImage(currentVideo, 0, 0, width, height)
              const imageData = ctx.getImageData(0, 0, width, height)
              const code = jsQR(imageData.data, width, height, {
                inversionAttempts: 'dontInvert',
              })

              if (code?.data) {
                detectedRef.current = true
                onDetect(code.data.trim())
                return
              }
            }
          }

          rafRef.current = requestAnimationFrame(tick)
        }

        rafRef.current = requestAnimationFrame(tick)
      } catch (error) {
        setCameraError(getCameraErrorMessage(error))
      } finally {
        if (!cancelled) setStarting(false)
      }
    }

    startScanner()

    return () => {
      cancelled = true
      detectedRef.current = true
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
        streamRef.current = null
      }
      const video = videoRef.current
      if (video) {
        video.pause()
        video.srcObject = null
      }
    }
  }, [open, onDetect])

  if (!open) return null

  return (
    <div className="scanner-backdrop" role="dialog" aria-modal="true" aria-label="Escáner QR">
      <div className="scanner-panel">
        <div className="scanner-header">
          <div>
            <div className="panel-title">⌖ Escáner QR</div>
            <p className="scanner-copy">Apunta la cámara trasera al código QR del asset y mantén el teléfono estable unos segundos.</p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Cerrar
          </button>
        </div>

        <div className="scanner-viewport">
          <video ref={videoRef} className="scanner-video" muted />
          <div className="scanner-frame" aria-hidden="true" />
          {starting && <div className="scanner-status">Abriendo cámara…</div>}
        </div>

        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {cameraError ? (
          <div className="alert alert-error">{cameraError}</div>
        ) : (
          <p className="scanner-hint">
            Si el escaneo falla, cierra el panel y usa la búsqueda manual con serial, código interno o valor QR.
          </p>
        )}
      </div>
    </div>
  )
}

function formatDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
  })
}

function HistoryStatusBadge({ status }) {
  return (
    <span className={`badge history-status-${status || 'unknown'}`}>
      {status || 'unknown'}
    </span>
  )
}

function MaintenanceHistoryPanel({ assetId }) {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true

    async function loadHistory() {
      if (!assetId) return
      setLoading(true)
      setError(null)
      try {
        const res = await api.getAssetHistory(assetId, { skip: 0, limit: 50 })
        if (!alive) return
        setItems(res.items || [])
        setTotal(res.total || 0)
      } catch (e) {
        if (alive) setError(e.message)
      } finally {
        if (alive) setLoading(false)
      }
    }

    loadHistory()
    return () => { alive = false }
  }, [assetId])

  return (
    <div className="maintenance-history">
      <div className="maintenance-history-header">
        <div>
          <span className="panel-title">Maintenance History</span>
          <p className="helper-text">Newest interventions linked to this asset.</p>
        </div>
        {!loading && <span className="page-count">{total} records</span>}
      </div>

      {error && <div className="alert alert-error mt-3">{error}</div>}

      {loading ? (
        <Loading label="Loading maintenance history..." />
      ) : items.length === 0 ? (
        <Empty icon="⬒" message="No maintenance history yet." />
      ) : (
        <div className="table-wrap">
          <table className="responsive-table maintenance-history-table">
            <thead>
              <tr>
                <th>Intervention</th>
                <th>Status</th>
                <th>Created</th>
                <th>Closed</th>
                <th>Technician</th>
                <th>Evidence</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.intervention_id}>
                  <td data-label="Intervention" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                    {item.title}
                  </td>
                  <td data-label="Status"><HistoryStatusBadge status={item.status} /></td>
                  <td data-label="Created" className="mono text-muted">{formatDateTime(item.created_at)}</td>
                  <td data-label="Closed" className="mono text-muted">{formatDate(item.closed_at)}</td>
                  <td data-label="Technician">{item.associated_technician || '—'}</td>
                  <td data-label="Evidence" className="mono">{item.evidence_count}</td>
                  <td data-label="Action">
                    <Link className="btn btn-ghost btn-sm" to={`/interventions/${item.intervention_id}`}>
                      Open
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default function AssetsPage() {
  const [assets, setAssets] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [scanCode, setScanCode] = useState('')
  const [scanResult, setScanResult] = useState(null)
  const [scanSuccess, setScanSuccess] = useState(null)
  const [scanError, setScanError] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [scannerOpen, setScannerOpen] = useState(false)
  const scanResultRef = useRef(null)
  const LIMIT = 50

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await api.getAssets({ skip, limit: LIMIT, search: search || undefined, status: statusFilter || undefined })
      setAssets(res.items); setTotal(res.total)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [skip, search, statusFilter])

  useEffect(() => { load() }, [load])
  useEffect(() => { setSkip(0) }, [search, statusFilter])
  useEffect(() => {
    if (!scanResult || !scanResultRef.current) return
    scanResultRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [scanResult])

  async function handleScan(e) {
    e.preventDefault()
    if (!scanCode.trim()) return
    await runScan(scanCode.trim())
  }

  async function runScan(code) {
    setScanning(true)
    setScanResult(null)
    setScanSuccess(null)
    setScanError(null)

    try {
      const asset = await api.scanAsset(code)
      setScanCode(code)
      setScanResult(asset)
      setScanSuccess(`Código detectado. Se encontró el equipo ${asset.item_name}.`)
      setScannerOpen(false)
    } catch (e) {
      setScanError(`No se encontró un equipo con ese código. ${e.message}`)
    } finally {
      setScanning(false)
    }
  }

  function openScanner() {
    setScanError(null)
    setScanSuccess(null)
    setScannerOpen(true)
  }

  function closeScanner() {
    setScannerOpen(false)
  }

  async function downloadQr(asset) {
    try {
      await api.downloadAssetQr(asset.id)
    } catch (e) {
      setScanError(e.message)
    }
  }

  return (
    <>
      <ScannerModal
        open={scannerOpen}
        onClose={closeScanner}
        onDetect={runScan}
      />

      <div className="page-header">
        <h1 className="page-title">// ASSETS</h1>
        {!loading && <span className="page-count">{total} equipos</span>}
      </div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">⌖ Buscar por código / QR</span></div>
        <div className="panel-body">
          <p className="helper-text" style={{ marginBottom: 12 }}>
            Usa la cámara para leer un QR del asset o escribe manualmente serial, código interno o valor QR.
          </p>
          <form onSubmit={handleScan} className="scan-form">
            <input value={scanCode} onChange={e => setScanCode(e.target.value)}
              className="touch-input"
              placeholder="SGOI-ASSET-42, SN-001, INT-ABC..." enterKeyHint="search" />
            <button className="btn btn-primary" disabled={scanning || !scanCode.trim()}>
              {scanning ? 'Buscando…' : 'Buscar código'}
            </button>
            <button type="button" className="btn btn-scan" onClick={openScanner} disabled={scanning}>
              📷 Escanear con cámara
            </button>
            {scanResult && <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => { setScanResult(null); setScanCode(''); setScanSuccess(null); setScanError(null) }}>✕ Limpiar</button>}
          </form>
          {scanSuccess && <div className="alert alert-success mt-3">{scanSuccess}</div>}
          {scanError && <div className="alert alert-error mt-3">{scanError}</div>}
          {scanResult && (
            <div ref={scanResultRef} className="mt-3">
              <div className="scan-result-card">
                <div>
                  <div className="flex gap-3 items-center" style={{marginBottom:6}}>
                    <span style={{fontWeight:600,color:'var(--text-primary)'}}>{scanResult.item_name}</span>
                    <StatusBadge status={scanResult.status} />
                  </div>
                  <div className="flex gap-4 text-mono text-muted">
                    <span>ID: {scanResult.id}</span>
                    {scanResult.part?.part_number && <span>PN: {scanResult.part.part_number}</span>}
                    {scanResult.serial_number && <span>SN: {scanResult.serial_number}</span>}
                    {scanResult.internal_code && <span>INT: {scanResult.internal_code}</span>}
                    <span style={{color:'var(--amber)'}}>{scanResult.qr_code_value}</span>
                  </div>
                </div>
                <div className="scan-result-actions">
                  <button className="btn btn-ghost btn-sm" onClick={() => downloadQr(scanResult)}>⬇ QR</button>
                </div>
              </div>
              <DocsBridgePanel asset={scanResult} />
              <MaintenanceHistoryPanel assetId={scanResult.id} />
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▤ Inventario</span>
          <div className="search-bar">
            <input value={search} onChange={e => setSearch(e.target.value)}
              className="touch-input"
              placeholder="Buscar nombre, serial, código..." style={{maxWidth:240}} />
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="touch-input" style={{width:160}}>
              <option value="">Todos los estados</option>
              <option value="available">Disponible</option>
              <option value="in_use">En Uso</option>
              <option value="maintenance">Mantenimiento</option>
              <option value="retired">Retirado</option>
              <option value="unknown">Desconocido</option>
            </select>
            <button className="btn btn-ghost btn-sm" onClick={load}>↺</button>
          </div>
        </div>
        {error && <div className="alert alert-error" style={{margin:16}}>{error}</div>}
        <div className="table-wrap">
          {loading ? <Loading /> : assets.length === 0 ? <Empty icon="⬡" message="Sin equipos" /> : (
            <table className="responsive-table">
              <thead><tr>
                <th>ID</th><th>Nombre</th><th>Part Number</th>
                <th>Serial / Código</th><th>Estado</th><th>Ubicación</th><th>Docs</th><th>QR</th><th>QR Value</th>
              </tr></thead>
              <tbody>
                {assets.map(a => (
                  <tr key={a.id}>
                    <td data-label="ID" className="mono text-muted">{a.id}</td>
                    <td data-label="Nombre" style={{color:'var(--text-primary)',fontWeight:500}}>{a.item_name}</td>
                    <td data-label="Part Number" className="mono">{a.part?.part_number ?? '—'}</td>
                    <td data-label="Serial / Código" className="mono">
                      {a.serial_number && <div style={{color:'var(--cyan)'}}>{a.serial_number}</div>}
                      {a.internal_code && <div style={{color:'var(--text-muted)'}}>{a.internal_code}</div>}
                    </td>
                    <td data-label="Estado"><StatusBadge status={a.status} /></td>
                    <td data-label="Ubicación" className="text-muted">{a.location ?? '—'}</td>
                    <td data-label="Docs">
                      <Link className="btn btn-ghost btn-sm btn-icon" title="Open in SGOI Docs"
                        to={docsPortalPathForAsset(a)}>▧</Link>
                    </td>
                    <td data-label="QR"><button className="btn btn-ghost btn-sm btn-icon" title="Descargar QR"
                      onClick={() => downloadQr(a)}>⬇</button></td>
                    <td data-label="QR Value" className="mono" style={{color:'var(--amber)',fontSize:11}}>{a.qr_code_value}</td>
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
