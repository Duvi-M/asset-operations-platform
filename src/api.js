const BASE = '/api/v1'

async function req(url, opts = {}) {
  const res = await fetch(BASE + url, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Error desconocido')
  }
  return res
}

async function json(url, opts = {}) {
  return (await req(url, opts)).json()
}

// ── Assets ────────────────────────────────────────────────────────────────────
export const api = {
  // Assets
  getAssets: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    )
    return json(`/assets${q.size ? '?' + q : ''}`)
  },
  getAsset: (id) => json(`/assets/${id}`),
  scanAsset: (code) => json(`/assets/scan/${encodeURIComponent(code)}`),
  getAssetQrUrl: (id) => `${BASE}/assets/${id}/qr`,

  // Parts
  getParts: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    )
    return json(`/parts${q.size ? '?' + q : ''}`)
  },

  // Import
  importExcel: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return json('/import/excel', { method: 'POST', body: fd })
  },

  // Interventions
  getInterventions: (params = {}) => {
    const q = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
    )
    return json(`/interventions${q.size ? '?' + q : ''}`)
  },
  getIntervention: (id) => json(`/interventions/${id}`),
  createIntervention: (data) =>
    json('/interventions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  updateIntervention: (id, data) =>
    json(`/interventions/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  // Intervention assets
  addAssetToIntervention: (interventionId, data) =>
    json(`/interventions/${interventionId}/assets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  // Evidence
  getEvidence: (interventionId) => json(`/interventions/${interventionId}/evidence`),
  uploadEvidence: (interventionId, file) => {
    const fd = new FormData()
    fd.append('file', file)
    return json(`/interventions/${interventionId}/evidence`, { method: 'POST', body: fd })
  },

  // PDF
  getPdfUrl: (interventionId) => `${BASE}/interventions/${interventionId}/pdf`,
}
