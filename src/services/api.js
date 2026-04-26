const BASE = '/api/v1'

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res
}

async function json(path, opts = {}) {
  const res = await req(path, { ...opts, headers: { 'Content-Type': 'application/json', ...opts.headers } })
  return res.json()
}

// ── Assets ────────────────────────────────────────────────────────────────────
export const api = {
  // Assets
  listAssets: (params = {}) => {
    const q = new URLSearchParams()
    if (params.search)  q.set('search', params.search)
    if (params.status)  q.set('status', params.status)
    if (params.skip)    q.set('skip', params.skip)
    if (params.limit)   q.set('limit', params.limit ?? 50)
    return json(`/assets?${q}`)
  },
  getAsset: (id) => json(`/assets/${id}`),
  scanAsset: (code) => json(`/assets/scan/${encodeURIComponent(code)}`),
  createAsset: (data) => json('/assets', { method: 'POST', body: JSON.stringify(data) }),
  updateAsset: (id, data) => json(`/assets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  qrUrl: (id) => `${BASE}/assets/${id}/qr`,

  // Parts
  listParts: (params = {}) => {
    const q = new URLSearchParams()
    if (params.search) q.set('search', params.search)
    return json(`/parts?${q}`)
  },

  // Interventions
  listInterventions: (params = {}) => {
    const q = new URLSearchParams()
    if (params.skip)  q.set('skip', params.skip)
    if (params.limit) q.set('limit', params.limit ?? 50)
    return json(`/interventions?${q}`)
  },
  getIntervention: (id) => json(`/interventions/${id}`),
  createIntervention: (data) => json('/interventions', { method: 'POST', body: JSON.stringify(data) }),
  updateIntervention: (id, data) => json(`/interventions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  addAssetToIntervention: (id, data) => json(`/interventions/${id}/assets`, { method: 'POST', body: JSON.stringify(data) }),

  // Evidence
  listEvidence: (id) => json(`/interventions/${id}/evidence`),
  uploadEvidence: async (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await req(`/interventions/${id}/evidence`, { method: 'POST', body: fd })
    return res.json()
  },

  // PDF — returns blob URL
  pdfUrl: (id) => `${BASE}/interventions/${id}/pdf`,

  // Import
  importExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await req('/import/excel', { method: 'POST', body: fd })
    return res.json()
  },
}
