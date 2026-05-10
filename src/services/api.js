const PROD_API_URL = 'https://project-nov.onrender.com'
const ENV_API_URL = (import.meta.env.VITE_API_URL || '').trim()
const API_URL = ENV_API_URL || (import.meta.env.DEV ? '' : PROD_API_URL)
const DOCS_BASE_URL = ENV_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : PROD_API_URL)
const BASE = `${API_URL}/api/v1`
const AUTH_STORAGE_KEY = 'sgoi_auth'

function getStoredSession() {
  if (typeof window === 'undefined') return null
  try {
    const raw = window.localStorage.getItem(AUTH_STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function clearStoredSession() {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(AUTH_STORAGE_KEY)
}

function getAuthHeaders(headers = {}) {
  const session = getStoredSession()
  if (!session?.token) return headers
  return { ...headers, Authorization: `Bearer ${session.token}` }
}

async function req(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: getAuthHeaders(opts.headers),
  })
  if (!res.ok) {
    if (res.status === 401) {
      clearStoredSession()
      window.dispatchEvent(new Event('auth:logout'))
    }
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res
}

async function json(path, opts = {}) {
  const headers = opts.body instanceof FormData
    ? opts.headers
    : { 'Content-Type': 'application/json', ...opts.headers }

  const res = await req(path, { ...opts, headers })
  return res.json()
}

function makeQuery(params = {}) {
  const q = new URLSearchParams(
    Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
  )
  return q.size ? `?${q}` : ''
}

async function download(path, filename) {
  const res = await req(path)
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

export const api = {
  baseUrl: API_URL || window.location.origin,
  docsUrl: `${DOCS_BASE_URL}/docs`,
  storageKey: AUTH_STORAGE_KEY,

  // Auth
  login: (email, password) => json('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  getMe: () => json('/auth/me'),

  // Assets
  getAssets: (params = {}) => json(`/assets${makeQuery(params)}`),
  listAssets: (params = {}) => json(`/assets${makeQuery(params)}`),
  getAsset: (id) => json(`/assets/${id}`),
  scanAsset: (code) => json(`/assets/scan/${encodeURIComponent(code)}`),
  createAsset: (data) => json('/assets', { method: 'POST', body: JSON.stringify(data) }),
  updateAsset: (id, data) => json(`/assets/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  getAssetQrUrl: (id) => `${BASE}/assets/${id}/qr`,
  qrUrl: (id) => `${BASE}/assets/${id}/qr`,
  downloadAssetQr: (id) => download(`/assets/${id}/qr`, `qr_asset_${id}.png`),

  // Parts
  getParts: (params = {}) => json(`/parts${makeQuery(params)}`),
  listParts: (params = {}) => json(`/parts${makeQuery(params)}`),

  // Interventions
  getInterventions: (params = {}) => json(`/interventions${makeQuery(params)}`),
  listInterventions: (params = {}) => json(`/interventions${makeQuery(params)}`),
  getIntervention: (id) => json(`/interventions/${id}`),
  createIntervention: (data) => json('/interventions', { method: 'POST', body: JSON.stringify(data) }),
  updateIntervention: (id, data) => json(`/interventions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  addAssetToIntervention: (id, data) => json(`/interventions/${id}/assets`, { method: 'POST', body: JSON.stringify(data) }),

  // Evidence
  getEvidence: (id) => json(`/interventions/${id}/evidence`),
  listEvidence: (id) => json(`/interventions/${id}/evidence`),
  uploadEvidence: async (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await req(`/interventions/${id}/evidence`, { method: 'POST', body: fd })
    return res.json()
  },

  // PDF
  getPdfUrl: (id) => `${BASE}/interventions/${id}/pdf`,
  pdfUrl: (id) => `${BASE}/interventions/${id}/pdf`,
  downloadPdf: (id) => download(`/interventions/${id}/pdf`, `intervencion_${id}.pdf`),

  // Import
  importExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await req('/import/excel', { method: 'POST', body: fd })
    return res.json()
  },
}
