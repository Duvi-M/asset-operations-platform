import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import { StatusBadge, Loading, Empty, Pagination } from '../components/ui'

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
  const [scanError, setScanError] = useState(null)
  const [scanning, setScanning] = useState(false)
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

  async function handleScan(e) {
    e.preventDefault()
    if (!scanCode.trim()) return
    setScanning(true); setScanResult(null); setScanError(null)
    try { setScanResult(await api.scanAsset(scanCode.trim())) }
    catch (e) { setScanError(e.message) }
    finally { setScanning(false) }
  }

  function downloadQr(asset) {
    const a = document.createElement('a')
    a.href = api.getAssetQrUrl(asset.id)
    a.download = `qr_asset_${asset.id}.png`
    a.click()
  }

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// ASSETS</h1>
        {!loading && <span className="page-count">{total} equipos</span>}
      </div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">⌖ Buscar por código / QR</span></div>
        <div className="panel-body">
          <form onSubmit={handleScan} className="flex gap-3" style={{flexWrap:'wrap'}}>
            <input value={scanCode} onChange={e => setScanCode(e.target.value)}
              placeholder="SGOI-ASSET-42, SN-001, INT-ABC..." style={{maxWidth:340}} />
            <button className="btn btn-primary" disabled={scanning || !scanCode.trim()}>
              {scanning ? 'Buscando…' : '⌖ Escanear'}
            </button>
            {scanResult && <button type="button" className="btn btn-ghost btn-sm"
              onClick={() => { setScanResult(null); setScanCode('') }}>✕ Limpiar</button>}
          </form>
          {scanError && <div className="alert alert-error mt-3">{scanError}</div>}
          {scanResult && (
            <div className="mt-3" style={{background:'var(--bg-card)',border:'1px solid var(--amber)',
              borderRadius:'var(--radius-lg)',padding:'14px 16px',display:'flex',
              alignItems:'center',justifyContent:'space-between',gap:12}}>
              <div>
                <div className="flex gap-3 items-center" style={{marginBottom:6}}>
                  <span style={{fontWeight:600,color:'var(--text-primary)'}}>{scanResult.item_name}</span>
                  <StatusBadge status={scanResult.status} />
                </div>
                <div className="flex gap-4 text-mono text-muted">
                  <span>ID: {scanResult.id}</span>
                  {scanResult.serial_number && <span>SN: {scanResult.serial_number}</span>}
                  {scanResult.internal_code && <span>INT: {scanResult.internal_code}</span>}
                  <span style={{color:'var(--amber)'}}>{scanResult.qr_code_value}</span>
                </div>
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => downloadQr(scanResult)}>⬇ QR</button>
            </div>
          )}
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▤ Inventario</span>
          <div className="search-bar">
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Buscar nombre, serial, código..." style={{maxWidth:240}} />
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{width:160}}>
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
            <table>
              <thead><tr>
                <th>ID</th><th>Nombre</th><th>Part Number</th>
                <th>Serial / Código</th><th>Estado</th><th>Ubicación</th><th>QR</th><th>QR Value</th>
              </tr></thead>
              <tbody>
                {assets.map(a => (
                  <tr key={a.id}>
                    <td className="mono text-muted">{a.id}</td>
                    <td style={{color:'var(--text-primary)',fontWeight:500}}>{a.item_name}</td>
                    <td className="mono">{a.part?.part_number ?? '—'}</td>
                    <td className="mono">
                      {a.serial_number && <div style={{color:'var(--cyan)'}}>{a.serial_number}</div>}
                      {a.internal_code && <div style={{color:'var(--text-muted)'}}>{a.internal_code}</div>}
                    </td>
                    <td><StatusBadge status={a.status} /></td>
                    <td className="text-muted">{a.location ?? '—'}</td>
                    <td><button className="btn btn-ghost btn-sm btn-icon" title="Descargar QR"
                      onClick={() => downloadQr(a)}>⬇</button></td>
                    <td className="mono" style={{color:'var(--amber)',fontSize:11}}>{a.qr_code_value}</td>
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
