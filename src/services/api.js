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

async function openBlob(path, filename, { download: shouldDownload = false } = {}) {
  const res = await req(path)
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)

  if (shouldDownload) {
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
  } else {
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  window.setTimeout(() => window.URL.revokeObjectURL(url), 60000)
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
  getAssetHistory: (id, params = {}) => json(`/assets/${id}/history${makeQuery(params)}`),
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

  // Work Orders
  getWorkOrders: (params = {}) => json(`/work-orders${makeQuery(params)}`),
  listWorkOrders: (params = {}) => json(`/work-orders${makeQuery(params)}`),
  getWorkOrder: (id) => json(`/work-orders/${id}`),
  createWorkOrder: (data) => json('/work-orders', { method: 'POST', body: JSON.stringify(data) }),
  updateWorkOrder: (id, data) => json(`/work-orders/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

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

  // SGOI Docs
  searchDocs: (params = {}) => json(`/docs/search${makeQuery(params)}`),
  listDocs: (params = {}) => json(`/docs/documents${makeQuery(params)}`),
  createDoc: (data) => json('/docs/documents', { method: 'POST', body: JSON.stringify(data) }),
  getDoc: (id) => json(`/docs/documents/${id}`),
  updateDoc: (id, data) => json(`/docs/documents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  uploadDocFile: async (id, file) => {
    const fd = new FormData()
    fd.append('file', file)
    const res = await req(`/docs/documents/${id}/file`, { method: 'POST', body: fd })
    return res.json()
  },
  getDocFile: (id) => json(`/docs/documents/${id}/file`),
  openDocFile: (id, filename = `sgoi_doc_${id}`) => openBlob(`/docs/documents/${id}/file/open`, filename),
  downloadDocFile: (id, filename = `sgoi_doc_${id}`) => openBlob(`/docs/documents/${id}/file/open?download=true`, filename, { download: true }),
  addDocReference: (id, data) => json(`/docs/documents/${id}/references`, { method: 'POST', body: JSON.stringify(data) }),
  addRelatedDoc: (id, data) => json(`/docs/documents/${id}/related`, { method: 'POST', body: JSON.stringify(data) }),
  getRelatedDocs: (id) => json(`/docs/documents/${id}/related`),
  getDocsByReference: (referenceType, referenceValue, params = {}) =>
    json(`/docs/references/${encodeURIComponent(referenceType)}/${encodeURIComponent(referenceValue)}${makeQuery(params)}`),

  // SGOI Docs Technical Catalog
  getTechnicalItems: (params = {}) => json(`/docs/items${makeQuery(params)}`),
  resolveTechnicalItems: (params = {}) => json(`/docs/items/resolve${makeQuery(params)}`),
  createTechnicalItem: (data) => json('/docs/items', { method: 'POST', body: JSON.stringify(data) }),
  getTechnicalItem: (id) => json(`/docs/items/${id}`),
  getTechnicalItemPacket: (id) => json(`/docs/items/${id}/packet`),
  updateTechnicalItem: (id, data) => json(`/docs/items/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  attachTechnicalItemDocument: (id, data) => json(`/docs/items/${id}/documents`, { method: 'POST', body: JSON.stringify(data) }),
  detachTechnicalItemDocument: async (id, documentId) => {
    await req(`/docs/items/${id}/documents/${documentId}`, { method: 'DELETE' })
  },
}
