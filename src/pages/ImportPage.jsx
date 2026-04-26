import { useState, useRef } from 'react'
import { api } from '../api'
import { Alert } from '../components/ui'

export default function ImportPage() {
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const inputRef = useRef()

  function onFile(f) {
    if (!f) return
    if (!f.name.endsWith('.xlsx')) { setError('Solo se aceptan archivos .xlsx'); return }
    setFile(f); setResult(null); setError(null)
  }
  function onDrop(e) { e.preventDefault(); setDragging(false); onFile(e.dataTransfer.files[0]) }

  async function handleImport() {
    if (!file) return
    setLoading(true); setResult(null); setError(null)
    try { setResult(await api.importExcel(file)) }
    catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <>
      <div className="page-header"><h1 className="page-title">// IMPORTAR EXCEL</h1></div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">⬆ Cargar archivo TAT</span></div>
        <div className="panel-body" style={{display:'flex',flexDirection:'column',gap:16}}>
          <div className={`upload-zone${dragging ? ' drag-over' : ''}`}
            onClick={() => inputRef.current.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}>
            <div className="upload-zone-icon">📊</div>
            {file ? (
              <><p><strong>{file.name}</strong></p>
                <p style={{marginTop:4}}>{(file.size/1024).toFixed(0)} KB — listo para importar</p></>
            ) : (
              <><p>Arrastra el archivo aquí o <strong>haz clic para seleccionar</strong></p>
                <p style={{marginTop:4,color:'var(--text-muted)'}}>Solo archivos .xlsx · máx. 20 MB</p></>
            )}
            <input ref={inputRef} type="file" accept=".xlsx" style={{display:'none'}}
              onChange={e => onFile(e.target.files[0])} />
          </div>
          {error && <Alert type="error">{error}</Alert>}
          <div className="flex gap-3">
            <button className="btn btn-primary" disabled={!file || loading} onClick={handleImport}>
              {loading ? <><span className="spinner" style={{width:14,height:14}} /> Importando…</> : '⬆ Importar'}
            </button>
            {file && <button className="btn btn-ghost"
              onClick={() => { setFile(null); setResult(null); setError(null) }}>✕ Limpiar</button>}
          </div>
        </div>
      </div>

      {result && (
        <>
          <Alert type={result.success ? 'success' : 'error'}>
            {result.success ? `✓ Importación completada — hoja "${result.sheet}"` : `⚠ Importación con errores — "${result.sheet}"`}
          </Alert>

          <div className="stats-row">
            {[
              {v:result.total_rows, l:'Filas leídas', c:''},
              {v:result.parts_created, l:'Parts creados', c:'green'},
              {v:result.parts_reused, l:'Parts reutilizados', c:''},
              {v:result.assets_created, l:'Assets creados', c:'green'},
              {v:result.assets_updated, l:'Assets actualizados', c:'blue'},
              {v:result.rows_skipped, l:'Filas omitidas', c:''},
            ].map(({v,l,c}) => (
              <div key={l} className="stat-card">
                <div className={`stat-value${c ? ' '+c : ''}`}>{v}</div>
                <div className="stat-label">{l}</div>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">⎇ Columnas detectadas</span>
              {result.unrecognised_columns.length > 0 && (
                <span className="text-muted text-mono" style={{fontSize:11}}>
                  {result.unrecognised_columns.length} ignoradas
                </span>
              )}
            </div>
            <div className="panel-body">
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))',gap:8}}>
                {Object.entries(result.detected_columns).filter(([,v]) => v).map(([f,c]) => (
                  <div key={f} style={{display:'flex',gap:8,alignItems:'center'}}>
                    <span className="mono" style={{color:'var(--amber)',minWidth:120}}>{f}</span>
                    <span className="text-muted">←</span>
                    <span className="mono" style={{color:'var(--cyan)'}}>{c}</span>
                  </div>
                ))}
              </div>
              {result.unrecognised_columns.length > 0 && (
                <div className="mt-3">
                  <span className="text-muted text-mono" style={{fontSize:11}}>
                    Ignoradas: {result.unrecognised_columns.join(', ')}
                  </span>
                </div>
              )}
            </div>
          </div>

          {result.errors.length > 0 && (
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title" style={{color:'var(--red)'}}>⚠ Errores ({result.errors.length})</span>
              </div>
              <div className="panel-body">
                <div className="error-list">
                  {result.errors.map((e,i) => (
                    <div key={i} className="error-item">
                      <span className="error-row">Fila {e.row}</span>
                      {e.identifier && <span style={{color:'var(--text-secondary)'}}>{e.identifier}</span>}
                      <span>{e.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
