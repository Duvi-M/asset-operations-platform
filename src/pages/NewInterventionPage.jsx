import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../services/api'
import { Alert } from '../components/ui'

const TYPES = [
  {v:'installation', l:'Instalación'}, {v:'support', l:'Soporte'},
  {v:'maintenance', l:'Mantenimiento'}, {v:'inspection', l:'Inspección'},
  {v:'removal', l:'Retiro'}, {v:'other', l:'Otro'},
]

export default function NewInterventionPage() {
  const navigate = useNavigate()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [form, setForm] = useState({
    type: 'installation',
    rig: '',
    pozo: '',
    technician: '',
    date: new Date().toISOString().split('T')[0],
    end_date: '',
    description: '',
  })

  function set(k, v) { setForm(f => ({ ...f, [k]: v })) }

async function handleSubmit(e) {
  e.preventDefault()

  if (!form.rig || !form.pozo || !form.technician || !form.date) {
    setError('Completa todos los campos obligatorios')
    return
  }

  setSaving(true)
  setError(null)

  try {
    const payload = {
      ...form,
      end_date: form.end_date || null,
    }

    const res = await api.createIntervention(payload)
    navigate(`/interventions/${res.id}`, {
      state: {
        flash: {
          type: 'success',
          message: 'Intervención creada. Ahora puedes asociar equipos, tomar evidencias y descargar el PDF.',
        },
      },
    })
  } catch (e) {
    setError(e.message)
  } finally {
    setSaving(false)
  }
}

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// NUEVA INTERVENCIÓN</h1>
        <button className="btn btn-ghost" onClick={() => navigate('/interventions')}>← Volver</button>
      </div>

      <div className="panel">
        <div className="panel-header"><span className="panel-title">⬒ Datos del Reporte</span></div>
        <div className="panel-body">
          <form onSubmit={handleSubmit} style={{display:'flex',flexDirection:'column',gap:18}}>
            {error && <Alert type="error">{error}</Alert>}
            <Alert type="info">
              Completa lo esencial para crear el reporte y continuar. Luego podrás asociar equipos, tomar fotos y descargar el PDF.
            </Alert>

            <div className="field-row cols-3">
              <div className="field">
                <label>Tipo de Evento *</label>
                <select value={form.type} onChange={e => set('type', e.target.value)}>
                  {TYPES.map(t => <option key={t.v} value={t.v}>{t.l}</option>)}
                </select>
              </div>
              <div className="field">
                <label>RIG *</label>
                <input value={form.rig} onChange={e => set('rig', e.target.value)} placeholder="RIG-07" autoFocus autoCapitalize="characters" enterKeyHint="next" />
              </div>
              <div className="field">
                <label>Pozo *</label>
                <input value={form.pozo} onChange={e => set('pozo', e.target.value)} placeholder="POZO-A-14" autoCapitalize="characters" enterKeyHint="next" />
              </div>
            </div>

            <div className="field-row cols-3">
              <div className="field">
                <label>Técnico Responsable *</label>
                <input value={form.technician} onChange={e => set('technician', e.target.value)} placeholder="Nombre completo" autoCapitalize="words" autoComplete="name" enterKeyHint="next" />
              </div>
              <div className="field">
                <label>Fecha *</label>
                <input type="date" value={form.date} onChange={e => set('date', e.target.value)} />
              </div>
              <div className="field">
                <label>Fecha de Finalización</label>
                <input type="date" value={form.end_date} onChange={e => set('end_date', e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Descripción</label>
              <textarea value={form.description} onChange={e => set('description', e.target.value)}
                placeholder="Detalle breve de la intervención..." rows={4} enterKeyHint="done" />
            </div>

            <div className="mobile-actions mobile-action-bar">
              <button type="submit" className="btn btn-primary" disabled={saving}>
                {saving ? 'Guardando…' : '✓ Crear y continuar'}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/interventions')}>
                Cancelar
              </button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}
