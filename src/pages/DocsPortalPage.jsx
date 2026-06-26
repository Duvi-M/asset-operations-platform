import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../services/api'
import { Alert, Empty, Loading, Pagination } from '../components/ui'
import { useAuth } from '../auth/AuthContext'

const LIMIT = 50

const DOC_STATUS = [
  { value: '', label: 'All statuses' },
  { value: 'active', label: 'Active' },
  { value: 'draft', label: 'Draft' },
  { value: 'obsolete', label: 'Obsolete' },
]

const DOC_TYPES = ['', 'manual', 'certificate', 'procedure', 'datasheet', 'drawing', 'inspection_report', 'calibration']
const ITEM_STATUSES = ['', 'active', 'draft', 'obsolete', 'inactive']
const ITEM_RELATIONS = ['manual', 'certificate', 'diagram', 'procedure', 'datasheet', 'report', 'related']

const REFERENCE_TYPES = [
  { value: 'part_number', label: 'Part Number' },
  { value: 'item_id', label: 'Item ID' },
  { value: 'serial_number', label: 'Serial Number' },
  { value: 'internal_code', label: 'Internal Code' },
  { value: 'asset_id', label: 'Asset ID' },
  { value: 'part_id', label: 'Part ID' },
  { value: 'model', label: 'Model' },
  { value: 'manufacturer_code', label: 'Manufacturer Code' },
]

const RELATION_LABELS = {
  supersedes: 'Supersedes',
  replaces: 'Replaces',
  references: 'References',
  same_equipment: 'Same equipment',
  certificate_for: 'Certificate for',
  procedure_for: 'Procedure for',
}

const SEARCH_CHIPS = [
  { label: 'Part Number', value: 'PN-' },
  { label: 'Item ID', value: 'ITEM-' },
  { label: 'Model', value: 'model' },
  { label: 'Manufacturer', value: 'NOV' },
  { label: 'Certificate', value: 'certificate' },
]

function pretty(value) {
  if (!value) return '—'
  return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: '2-digit' })
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

function formatBytes(value) {
  if (!value) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function DocStatusBadge({ status }) {
  return <span className={`badge docs-status docs-status-${status || 'unknown'}`}>{pretty(status)}</span>
}

function ItemStatusBadge({ status }) {
  return <span className={`badge docs-status docs-status-${status || 'unknown'}`}>{pretty(status)}</span>
}

function DetailItem({ label, value, mono = false }) {
  return (
    <div className="docs-detail-item">
      <span>{label}</span>
      <strong className={mono ? 'mono' : ''}>{value || '—'}</strong>
    </div>
  )
}

function makeEmptyDocForm() {
  return {
    document_code: '',
    title: '',
    description: '',
    document_type: 'manual',
    status: 'draft',
    revision: '',
    language: 'en',
    manufacturer: '',
    source_system: 'sgoi_docs',
    effective_date: '',
    expires_at: '',
  }
}

function makeEmptyItemForm() {
  return {
    item_id: '',
    part_number: '',
    name: '',
    model: '',
    manufacturer: '',
    manufacturer_code: '',
    category: '',
    equipment_family: '',
    description: '',
    source_system: 'sgoi_docs',
    status: 'active',
  }
}

function formFromItem(item) {
  return {
    item_id: item.item_id || '',
    part_number: item.part_number || '',
    name: item.name || '',
    model: item.model || '',
    manufacturer: item.manufacturer || '',
    manufacturer_code: item.manufacturer_code || '',
    category: item.category || '',
    equipment_family: item.equipment_family || '',
    description: item.description || '',
    source_system: item.source_system || 'sgoi_docs',
    status: item.status || 'active',
  }
}

function cleanPayload(data) {
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, value === '' ? null : value]))
}

function groupItemDocuments(documents = []) {
  return ITEM_RELATIONS.map((relation) => ({
    relation,
    documents: documents.filter((link) => link.relation_type === relation),
  }))
}

async function enrichDocuments(items) {
  if (!items.length) return []
  const details = await Promise.allSettled(items.map((doc) => api.getDoc(doc.id)))
  return items.map((doc, index) => (details[index].status === 'fulfilled' ? details[index].value : doc))
}

export default function DocsPortalPage() {
  const { isAdmin } = useAuth()
  const [urlSearchParams] = useSearchParams()
  const urlQuery = urlSearchParams.get('q') || ''
  const urlItemId = urlSearchParams.get('item_id') || ''
  const [activeTab, setActiveTab] = useState('catalog')

  const [itemQuery, setItemQuery] = useState(urlItemId || urlQuery)
  const [itemFilters, setItemFilters] = useState({ status: '', manufacturer: '', category: '' })
  const [items, setItems] = useState([])
  const [itemTotal, setItemTotal] = useState(0)
  const [itemSkip, setItemSkip] = useState(0)
  const [selectedItemId, setSelectedItemId] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)
  const [itemsLoading, setItemsLoading] = useState(true)
  const [itemDetailLoading, setItemDetailLoading] = useState(false)
  const [itemAdminOpen, setItemAdminOpen] = useState(false)
  const [itemEditing, setItemEditing] = useState(false)
  const [itemForm, setItemForm] = useState(() => makeEmptyItemForm())
  const [attachForm, setAttachForm] = useState({ document_id: '', relation_type: 'manual' })

  const [query, setQuery] = useState(urlQuery)
  const [filters, setFilters] = useState({ document_type: '', status: '', manufacturer: '' })
  const [docs, setDocs] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [selectedId, setSelectedId] = useState(null)
  const [selectedDoc, setSelectedDoc] = useState(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [adminOpen, setAdminOpen] = useState(false)
  const [form, setForm] = useState(() => makeEmptyDocForm())
  const [referenceForm, setReferenceForm] = useState({ reference_type: 'part_number', reference_value: '', label: '' })

  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [saving, setSaving] = useState(false)
  const [fileUploading, setFileUploading] = useState(false)

  const activeDocument = selectedDoc || docs.find((doc) => doc.id === selectedId)
  const adminCanEditSelection = isAdmin && selectedDoc

  const itemSearchParams = useMemo(() => ({
    skip: itemSkip,
    limit: LIMIT,
    search: itemQuery.trim() || undefined,
    status: itemFilters.status || undefined,
    manufacturer: itemFilters.manufacturer.trim() || undefined,
    category: itemFilters.category.trim() || undefined,
  }), [itemFilters, itemQuery, itemSkip])

  const docsSearchParams = useMemo(() => ({
    skip,
    limit: LIMIT,
    query: query.trim() || undefined,
    document_type: filters.document_type || undefined,
    status: filters.status || undefined,
    manufacturer: filters.manufacturer.trim() || undefined,
  }), [filters, query, skip])

  const loadItems = useCallback(async () => {
    setItemsLoading(true)
    setError(null)
    try {
      const res = await api.getTechnicalItems(itemSearchParams)
      setItems(res.items || [])
      setItemTotal(res.total || 0)
    } catch (e) {
      setError(e.message)
    } finally {
      setItemsLoading(false)
    }
  }, [itemSearchParams])

  const loadItemDetail = useCallback(async (id) => {
    if (!id) {
      setSelectedItem(null)
      return
    }
    setItemDetailLoading(true)
    setError(null)
    try {
      const item = await api.getTechnicalItem(id)
      setSelectedItem(item)
      setItemForm(formFromItem(item))
    } catch (e) {
      setError(e.message)
    } finally {
      setItemDetailLoading(false)
    }
  }, [])

  const loadDocs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const trimmedQuery = query.trim()
      if (trimmedQuery) {
        const [textResult, referenceResult] = await Promise.allSettled([
          api.searchDocs(docsSearchParams),
          api.searchDocs({ ...docsSearchParams, query: undefined, reference_value: trimmedQuery }),
        ])
        const raw = [
          ...(textResult.status === 'fulfilled' ? textResult.value.items || [] : []),
          ...(referenceResult.status === 'fulfilled' ? referenceResult.value.items || [] : []),
        ]
        const seen = new Set()
        const merged = raw.filter((doc) => {
          if (!doc?.id || seen.has(doc.id)) return false
          seen.add(doc.id)
          return true
        })
        setDocs(await enrichDocuments(merged))
        setTotal(merged.length)
      } else {
        const res = await api.searchDocs(docsSearchParams)
        setDocs(await enrichDocuments(res.items || []))
        setTotal(res.total || 0)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [query, docsSearchParams])

  const loadDetail = useCallback(async (id) => {
    if (!id) {
      setSelectedDoc(null)
      return
    }
    setDetailLoading(true)
    setError(null)
    try {
      setSelectedDoc(await api.getDoc(id))
    } catch (e) {
      setError(e.message)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => { loadItems() }, [loadItems])
  useEffect(() => { if (activeTab === 'documents') loadDocs() }, [activeTab, loadDocs])
  useEffect(() => {
    if (urlItemId) {
      setActiveTab('catalog')
      setItemQuery(urlItemId)
      setQuery('')
      return
    }
    setItemQuery(urlQuery)
    setQuery(urlQuery)
  }, [urlQuery, urlItemId])

  useEffect(() => {
    if (!urlItemId || !items.length) return
    const normalized = urlItemId.toLowerCase()
    const match = items.find((item) => (
      String(item.item_id || '').toLowerCase() === normalized ||
      String(item.part_number || '').toLowerCase() === normalized ||
      String(item.id) === urlItemId
    ))
    if (match && selectedItemId !== match.id) setSelectedItemId(match.id)
  }, [items, selectedItemId, urlItemId])
  useEffect(() => { setItemSkip(0) }, [itemQuery, itemFilters.status, itemFilters.manufacturer, itemFilters.category])
  useEffect(() => { setSkip(0) }, [query, filters.document_type, filters.status, filters.manufacturer])
  useEffect(() => { loadItemDetail(selectedItemId) }, [selectedItemId, loadItemDetail])
  useEffect(() => { loadDetail(selectedId) }, [selectedId, loadDetail])

  function setItemFilter(name, value) {
    setItemFilters((current) => ({ ...current, [name]: value }))
  }

  function setFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }))
  }

  function setItemFormValue(name, value) {
    setItemForm((current) => ({ ...current, [name]: value }))
  }

  function setFormValue(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  function selectItem(item) {
    setSelectedItemId(item.id)
    setSuccess(null)
    setItemEditing(false)
  }

  function selectDoc(doc) {
    setSelectedId(doc.id)
    setSuccess(null)
  }

  async function saveTechnicalItem(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = cleanPayload(itemForm)
      const item = itemEditing && selectedItem
        ? await api.updateTechnicalItem(selectedItem.id, payload)
        : await api.createTechnicalItem(payload)
      setSuccess(`Technical item ${item.item_id} saved.`)
      setSelectedItemId(item.id)
      setSelectedItem(item)
      setItemForm(formFromItem(item))
      setItemAdminOpen(false)
      setItemEditing(false)
      await loadItems()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function attachDocument(e) {
    e.preventDefault()
    if (!selectedItem || !attachForm.document_id) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await api.attachTechnicalItemDocument(selectedItem.id, {
        document_id: Number(attachForm.document_id),
        relation_type: attachForm.relation_type,
      })
      setAttachForm({ document_id: '', relation_type: 'manual' })
      await loadItemDetail(selectedItem.id)
      await loadItems()
      setSuccess('Document attached to technical item.')
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function detachDocument(documentId) {
    if (!selectedItem) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await api.detachTechnicalItemDocument(selectedItem.id, documentId)
      await loadItemDetail(selectedItem.id)
      await loadItems()
      setSuccess('Document detached from technical item.')
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleCreateDocument(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const doc = await api.createDoc(cleanPayload(form))
      setSuccess(`Document ${doc.document_code} created. Select it to upload the technical file.`)
      setForm(makeEmptyDocForm())
      setAdminOpen(false)
      setSelectedId(doc.id)
      await loadDocs()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleUploadFile(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !selectedDoc) return
    setFileUploading(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await api.uploadDocFile(selectedDoc.id, file)
      setSelectedDoc(res.document)
      setSuccess(`File ${res.file.filename} uploaded for ${res.document.document_code}.`)
      await loadDocs()
    } catch (err) {
      setError(err.message)
    } finally {
      setFileUploading(false)
    }
  }

  async function handleAddReference(e) {
    e.preventDefault()
    if (!selectedDoc || !referenceForm.reference_value.trim()) return
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      await api.addDocReference(selectedDoc.id, {
        reference_type: referenceForm.reference_type,
        reference_value: referenceForm.reference_value.trim(),
        label: referenceForm.label.trim() || null,
      })
      setReferenceForm({ reference_type: 'part_number', reference_value: '', label: '' })
      await loadDetail(selectedDoc.id)
      await loadDocs()
      setSuccess('Reference added to the document index.')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function openDocFileByDocument(doc, download = false) {
    if (!doc?.id) return
    setError(null)
    try {
      const fullDoc = doc.file ? doc : await api.getDoc(doc.id)
      if (!fullDoc.file) throw new Error('No file has been uploaded for this document.')
      if (download) {
        await api.downloadDocFile(fullDoc.id, fullDoc.file.filename)
      } else {
        await api.openDocFile(fullDoc.id, fullDoc.file.filename)
      }
    } catch (err) {
      setError(err.message)
    }
  }

  const selectedItemGroups = groupItemDocuments(selectedItem?.documents || [])

  return (
    <>
      <div className="docs-portal-hero">
        <div>
          <span className="docs-kicker">External Technical Service</span>
          <h1>SGOI Docs Portal</h1>
          <p>Technical catalog and controlled documentation service</p>
        </div>
        <div className="docs-hero-meta">
          <span>{activeTab === 'catalog' ? 'Catalog items' : 'Documents'}</span>
          <strong>{activeTab === 'catalog' ? itemTotal : total}</strong>
          <span>{isAdmin ? 'admin access' : 'read only'}</span>
        </div>
      </div>

      <div className="docs-tabs">
        <button className={activeTab === 'catalog' ? 'active' : ''} onClick={() => setActiveTab('catalog')}>
          Technical Catalog
        </button>
        <button className={activeTab === 'documents' ? 'active' : ''} onClick={() => setActiveTab('documents')}>
          Documents
        </button>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {activeTab === 'catalog' ? (
        <>
          <section className="docs-search-panel">
            <form onSubmit={(e) => { e.preventDefault(); loadItems() }} className="docs-search-form">
              <label className="docs-primary-search">
                <span>Search technical item</span>
                <input
                  value={itemQuery}
                  onChange={(e) => setItemQuery(e.target.value)}
                  placeholder="Search by Part Number, Item ID, Model, Manufacturer..."
                  enterKeyHint="search"
                  autoComplete="off"
                />
              </label>
              <div className="docs-search-chips">
                {SEARCH_CHIPS.map((chip) => (
                  <button className="docs-search-chip" key={chip.label} type="button" onClick={() => setItemQuery(chip.value)}>
                    {chip.label}
                  </button>
                ))}
              </div>
              <div className="docs-filter-grid">
                <div className="field">
                  <label>Status</label>
                  <select value={itemFilters.status} onChange={(e) => setItemFilter('status', e.target.value)}>
                    {ITEM_STATUSES.map((status) => <option key={status || 'all'} value={status}>{status ? pretty(status) : 'All statuses'}</option>)}
                  </select>
                </div>
                <div className="field">
                  <label>Manufacturer</label>
                  <input value={itemFilters.manufacturer} onChange={(e) => setItemFilter('manufacturer', e.target.value)} placeholder="NOV, Varco..." />
                </div>
                <div className="field">
                  <label>Category</label>
                  <input value={itemFilters.category} onChange={(e) => setItemFilter('category', e.target.value)} placeholder="Top drive, sensors..." />
                </div>
                <div className="docs-filter-actions">
                  <button className="btn btn-primary">Search</button>
                  <button className="btn btn-ghost" type="button" onClick={() => {
                    setItemQuery('')
                    setItemFilters({ status: '', manufacturer: '', category: '' })
                  }}>
                    Clear
                  </button>
                </div>
              </div>
            </form>
          </section>

          <div className="docs-layout">
            <section className="panel docs-results-panel">
              <div className="panel-header">
                <span className="panel-title">▤ Technical Catalog</span>
                <div className="mobile-actions">
                  {isAdmin && (
                    <button className="btn btn-ghost btn-sm docs-admin-toggle" onClick={() => {
                      setItemAdminOpen((open) => !open)
                      setItemEditing(false)
                      setItemForm(makeEmptyItemForm())
                    }}>
                      {itemAdminOpen ? 'Close admin tools' : 'Admin tools'}
                    </button>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={loadItems}>↺ Refresh</button>
                </div>
              </div>

              {isAdmin && itemAdminOpen && (
                <div className="docs-admin-box">
                  <form onSubmit={saveTechnicalItem} className="docs-admin-form">
                    <div className="field-row cols-3">
                      <div className="field"><label>Item ID</label><input required value={itemForm.item_id} onChange={(e) => setItemFormValue('item_id', e.target.value)} placeholder="ITEM-0001" /></div>
                      <div className="field"><label>Part Number</label><input value={itemForm.part_number} onChange={(e) => setItemFormValue('part_number', e.target.value)} placeholder="PN-12345" /></div>
                      <div className="field"><label>Name</label><input required value={itemForm.name} onChange={(e) => setItemFormValue('name', e.target.value)} placeholder="Top Drive Encoder" /></div>
                    </div>
                    <div className="field-row cols-3">
                      <div className="field"><label>Model</label><input value={itemForm.model} onChange={(e) => setItemFormValue('model', e.target.value)} /></div>
                      <div className="field"><label>Manufacturer</label><input value={itemForm.manufacturer} onChange={(e) => setItemFormValue('manufacturer', e.target.value)} /></div>
                      <div className="field"><label>Manufacturer Code</label><input value={itemForm.manufacturer_code} onChange={(e) => setItemFormValue('manufacturer_code', e.target.value)} /></div>
                    </div>
                    <div className="field-row cols-3">
                      <div className="field"><label>Category</label><input value={itemForm.category} onChange={(e) => setItemFormValue('category', e.target.value)} /></div>
                      <div className="field"><label>Equipment Family</label><input value={itemForm.equipment_family} onChange={(e) => setItemFormValue('equipment_family', e.target.value)} /></div>
                      <div className="field"><label>Status</label><input value={itemForm.status} onChange={(e) => setItemFormValue('status', e.target.value)} /></div>
                    </div>
                    <div className="field-row cols-2">
                      <div className="field"><label>Source System</label><input value={itemForm.source_system} onChange={(e) => setItemFormValue('source_system', e.target.value)} /></div>
                    </div>
                    <div className="field"><label>Description</label><textarea value={itemForm.description} onChange={(e) => setItemFormValue('description', e.target.value)} /></div>
                    <button className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : itemEditing ? 'Save technical item' : 'Create technical item'}</button>
                  </form>
                </div>
              )}

              <div className="table-wrap">
                {itemsLoading ? <Loading label="Searching Technical Catalog..." /> : items.length === 0 ? (
                  <Empty icon="▧" message="No technical items match this search" />
                ) : (
                  <table className="responsive-table">
                    <thead><tr>
                      <th>Part Number</th><th>Item ID</th><th>Name</th><th>Model</th><th>Manufacturer</th><th>Category</th><th>Status</th><th>Docs</th><th>Action</th>
                    </tr></thead>
                    <tbody>
                      {items.map((item) => (
                        <tr key={item.id} className={selectedItemId === item.id ? 'docs-row-active' : ''}>
                          <td data-label="Part Number" className="mono docs-code">{item.part_number || '—'}</td>
                          <td data-label="Item ID" className="mono">{item.item_id}</td>
                          <td data-label="Name" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{item.name}</td>
                          <td data-label="Model">{item.model || '—'}</td>
                          <td data-label="Manufacturer">{item.manufacturer || '—'}</td>
                          <td data-label="Category">{item.category || '—'}</td>
                          <td data-label="Status"><ItemStatusBadge status={item.status} /></td>
                          <td data-label="Docs" className="mono">{item.documents?.length || 0}</td>
                          <td data-label="Action"><button className="btn btn-primary btn-sm" onClick={() => selectItem(item)}>Open Item</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              {!itemsLoading && <div style={{ padding: '0 18px 14px' }}><Pagination skip={itemSkip} limit={LIMIT} total={itemTotal} onSkip={setItemSkip} /></div>}
            </section>

            <aside className="panel docs-detail-panel">
              <div className="panel-header">
                <span className="panel-title">⌁ Ficha Técnica</span>
                {itemDetailLoading && <span className="text-muted text-mono">Loading...</span>}
              </div>
              {!selectedItem ? (
                <Empty icon="⌕" message="Open a technical item to inspect catalog metadata and attached documents" />
              ) : (
                <div className="panel-body docs-detail-body">
                  <div className="docs-detail-heading">
                    <div>
                      <span className="docs-code mono">{selectedItem.part_number || selectedItem.item_id}</span>
                      <h2>{selectedItem.name}</h2>
                    </div>
                    <ItemStatusBadge status={selectedItem.status} />
                  </div>
                  <div className="detail-grid">
                    <DetailItem label="Part Number" value={selectedItem.part_number} mono />
                    <DetailItem label="Item ID" value={selectedItem.item_id} mono />
                    <DetailItem label="Model" value={selectedItem.model} />
                    <DetailItem label="Manufacturer" value={selectedItem.manufacturer} />
                    <DetailItem label="Manufacturer Code" value={selectedItem.manufacturer_code} mono />
                    <DetailItem label="Category" value={selectedItem.category} />
                    <DetailItem label="Equipment Family" value={selectedItem.equipment_family} />
                    <DetailItem label="Source System" value={selectedItem.source_system} mono />
                  </div>
                  <div className="docs-section"><h3>Description</h3><p>{selectedItem.description || 'No description recorded.'}</p></div>

                  <div className="docs-section">
                    <h3>Attached Documents</h3>
                    <div className="technical-item-doc-groups">
                      {selectedItemGroups.map((group) => (
                        <section className="packet-category" key={group.relation}>
                          <div className="packet-category-head"><span>{pretty(group.relation)}</span><strong>{group.documents.length}</strong></div>
                          {group.documents.length ? (
                            <div className="packet-doc-list">
                              {group.documents.map((link) => (
                                <div className="packet-doc technical-item-doc" key={link.id}>
                                  <div className="packet-doc-topline">
                                    <span className="mono docs-code">{link.document.document_code}</span>
                                    <DocStatusBadge status={link.document.status} />
                                  </div>
                                  <strong>{link.document.title}</strong>
                                  <div className="packet-doc-meta">
                                    <span>{pretty(link.document.document_type)}</span>
                                    <span>Rev {link.document.revision || '—'}</span>
                                  </div>
                                  <div className="mobile-actions">
                                    <button className="btn btn-primary btn-sm" onClick={() => openDocFileByDocument(link.document, false)}>Open</button>
                                    <button className="btn btn-ghost btn-sm" onClick={() => openDocFileByDocument(link.document, true)}>Download</button>
                                    {isAdmin && <button className="btn btn-danger btn-sm" disabled={saving} onClick={() => detachDocument(link.document_id)}>Detach</button>}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : <div className="packet-empty">No document attached</div>}
                        </section>
                      ))}
                    </div>
                  </div>

                  {isAdmin && (
                    <div className="docs-admin-tools">
                      <h3>Catalog Admin Tools</h3>
                      <div className="mobile-actions">
                        <button className="btn btn-ghost" onClick={() => {
                          setItemForm(formFromItem(selectedItem))
                          setItemEditing(true)
                          setItemAdminOpen(true)
                        }}>Edit technical item</button>
                      </div>
                      <form onSubmit={attachDocument} className="docs-reference-form">
                        <div className="field"><label>Document ID</label><input type="number" min="1" value={attachForm.document_id} onChange={(e) => setAttachForm((current) => ({ ...current, document_id: e.target.value }))} placeholder="123" /></div>
                        <div className="field"><label>Relation Type</label><select value={attachForm.relation_type} onChange={(e) => setAttachForm((current) => ({ ...current, relation_type: e.target.value }))}>{ITEM_RELATIONS.map((relation) => <option key={relation} value={relation}>{pretty(relation)}</option>)}</select></div>
                        <button className="btn btn-ghost" disabled={saving || !attachForm.document_id}>Attach document</button>
                      </form>
                    </div>
                  )}
                </div>
              )}
            </aside>
          </div>
        </>
      ) : (
        <>
          <section className="docs-search-panel">
            <form onSubmit={(e) => { e.preventDefault(); loadDocs() }} className="docs-search-form">
              <label className="docs-primary-search">
                <span>Document lookup</span>
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Document Code, Part Number, Serial, Manual, Certificate..." enterKeyHint="search" autoComplete="off" />
              </label>
              <div className="docs-filter-grid">
                <div className="field"><label>Document type</label><select value={filters.document_type} onChange={(e) => setFilter('document_type', e.target.value)}><option value="">All types</option>{DOC_TYPES.filter(Boolean).map((type) => <option value={type} key={type}>{pretty(type)}</option>)}</select></div>
                <div className="field"><label>Status</label><select value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>{DOC_STATUS.map((status) => <option value={status.value} key={status.value || 'all'}>{status.label}</option>)}</select></div>
                <div className="field"><label>Manufacturer</label><input value={filters.manufacturer} onChange={(e) => setFilter('manufacturer', e.target.value)} placeholder="NOV, Varco, Hydralift..." /></div>
                <div className="docs-filter-actions"><button className="btn btn-primary">Search</button><button className="btn btn-ghost" type="button" onClick={() => { setQuery(''); setFilters({ document_type: '', status: '', manufacturer: '' }) }}>Clear</button></div>
              </div>
            </form>
          </section>

          <div className="docs-layout">
            <section className="panel docs-results-panel">
              <div className="panel-header">
                <span className="panel-title">▤ Document Records</span>
                <div className="mobile-actions">
                  {isAdmin && <button className="btn btn-ghost btn-sm docs-admin-toggle" onClick={() => setAdminOpen((open) => !open)}>{adminOpen ? 'Close admin tools' : 'Admin tools'}</button>}
                  <button className="btn btn-ghost btn-sm" onClick={loadDocs}>↺ Refresh</button>
                </div>
              </div>

              {isAdmin && adminOpen && (
                <div className="docs-admin-box">
                  <form onSubmit={handleCreateDocument} className="docs-admin-form">
                    <div className="field-row cols-3">
                      <div className="field"><label>Document Code</label><input required value={form.document_code} onChange={(e) => setFormValue('document_code', e.target.value)} placeholder="NOV-MAN-001" /></div>
                      <div className="field"><label>Title</label><input required value={form.title} onChange={(e) => setFormValue('title', e.target.value)} placeholder="Top Drive Service Manual" /></div>
                      <div className="field"><label>Type</label><select value={form.document_type} onChange={(e) => setFormValue('document_type', e.target.value)}>{DOC_TYPES.filter(Boolean).map((type) => <option key={type} value={type}>{pretty(type)}</option>)}</select></div>
                    </div>
                    <div className="field-row cols-3">
                      <div className="field"><label>Status</label><select value={form.status} onChange={(e) => setFormValue('status', e.target.value)}><option value="draft">Draft</option><option value="active">Active</option><option value="obsolete">Obsolete</option></select></div>
                      <div className="field"><label>Revision</label><input value={form.revision} onChange={(e) => setFormValue('revision', e.target.value)} /></div>
                      <div className="field"><label>Language</label><input value={form.language} onChange={(e) => setFormValue('language', e.target.value)} /></div>
                    </div>
                    <div className="field-row cols-3">
                      <div className="field"><label>Manufacturer</label><input value={form.manufacturer} onChange={(e) => setFormValue('manufacturer', e.target.value)} /></div>
                      <div className="field"><label>Effective Date</label><input type="date" value={form.effective_date} onChange={(e) => setFormValue('effective_date', e.target.value)} /></div>
                      <div className="field"><label>Expires At</label><input type="datetime-local" value={form.expires_at} onChange={(e) => setFormValue('expires_at', e.target.value)} /></div>
                    </div>
                    <div className="field"><label>Description</label><textarea value={form.description} onChange={(e) => setFormValue('description', e.target.value)} /></div>
                    <button className="btn btn-primary" disabled={saving}>{saving ? 'Creating...' : 'Create metadata'}</button>
                  </form>
                </div>
              )}

              <div className="table-wrap">
                {loading ? <Loading label="Searching SGOI Docs..." /> : docs.length === 0 ? <Empty icon="▧" message="No technical documents match this search" /> : (
                  <div className="docs-record-list">
                    {docs.map((doc) => (
                      <article className={`docs-record${selectedId === doc.id ? ' docs-record-active' : ''}`} key={doc.id}>
                        <div className="docs-record-main">
                          <div className="docs-record-code-row"><span className="mono docs-code">{doc.document_code}</span><DocStatusBadge status={doc.status} /><span className={`docs-file-indicator${doc.file ? ' available' : ''}`}>{doc.file ? 'File available' : 'No file'}</span></div>
                          <h2>{doc.title}</h2>
                          <div className="docs-record-meta-grid"><span><strong>Type</strong>{pretty(doc.document_type)}</span><span><strong>Revision</strong>{doc.revision || '—'}</span><span><strong>Manufacturer</strong>{doc.manufacturer || '—'}</span><span><strong>Source System</strong>{doc.source_system || '—'}</span></div>
                          <div className="docs-record-refs">{(doc.item_references || []).slice(0, 4).map((ref) => <span className="docs-chip" key={ref.id || `${ref.reference_type}:${ref.reference_value}`}><strong>{pretty(ref.reference_type)}</strong><span>{ref.reference_value}</span></span>)}{!doc.item_references?.length && <span className="text-muted">No references indexed</span>}</div>
                        </div>
                        <div className="docs-record-actions"><button className="btn btn-primary btn-sm" onClick={() => selectDoc(doc)}>Open record</button>{doc.file && <><button className="btn btn-ghost btn-sm" onClick={() => openDocFileByDocument(doc, false)}>Open</button><button className="btn btn-ghost btn-sm" onClick={() => openDocFileByDocument(doc, true)}>Download</button></>}</div>
                      </article>
                    ))}
                  </div>
                )}
              </div>
              {!loading && <div style={{ padding: '0 18px 14px' }}><Pagination skip={skip} limit={LIMIT} total={total} onSkip={setSkip} /></div>}
            </section>

            <aside className="panel docs-detail-panel">
              <div className="panel-header"><span className="panel-title">⌁ Document Ficha</span>{detailLoading && <span className="text-muted text-mono">Loading...</span>}</div>
              {!activeDocument ? <Empty icon="⌕" message="Select a document to inspect metadata, references, and file status" /> : (
                <div className="panel-body docs-detail-body">
                  <div className="docs-detail-heading"><div><span className="docs-code mono">{activeDocument.document_code}</span><h2>{activeDocument.title}</h2></div><DocStatusBadge status={activeDocument.status} /></div>
                  <div className="detail-grid">
                    <DetailItem label="Type" value={pretty(activeDocument.document_type)} />
                    <DetailItem label="Revision" value={activeDocument.revision} mono />
                    <DetailItem label="Language" value={activeDocument.language} mono />
                    <DetailItem label="Manufacturer" value={activeDocument.manufacturer} />
                    <DetailItem label="Source" value={activeDocument.source_system} mono />
                    <DetailItem label="Effective" value={formatDate(activeDocument.effective_date)} mono />
                    <DetailItem label="Expires" value={formatDateTime(activeDocument.expires_at)} mono />
                    <DetailItem label="Updated" value={formatDateTime(activeDocument.updated_at)} mono />
                  </div>
                  <div className="docs-section"><h3>Description</h3><p>{activeDocument.description || 'No description recorded.'}</p></div>
                  <div className="docs-section"><h3>Item References</h3>{selectedDoc?.item_references?.length ? <div className="docs-chip-list">{selectedDoc.item_references.map((ref) => <span className="docs-chip" key={ref.id}><strong>{pretty(ref.reference_type)}</strong><span>{ref.reference_value}</span>{ref.label && <em>{ref.label}</em>}</span>)}</div> : <p>No item references indexed.</p>}</div>
                  <div className="docs-section"><h3>Related Documents</h3>{selectedDoc?.related_out?.length ? <div className="docs-related-list">{selectedDoc.related_out.map((rel) => <button className="docs-related" key={rel.id} onClick={() => setSelectedId(rel.related_document_id)}><span>{RELATION_LABELS[rel.relation_type] || pretty(rel.relation_type)}</span><strong>{rel.related_document.document_code}</strong><em>{rel.related_document.title}</em></button>)}</div> : <p>No related documents linked.</p>}</div>
                  <div className="docs-section docs-file-card"><h3>File Metadata</h3>{selectedDoc?.file ? <><div className="detail-grid"><DetailItem label="Filename" value={selectedDoc.file.filename} /><DetailItem label="MIME" value={selectedDoc.file.mime_type} mono /><DetailItem label="Size" value={formatBytes(selectedDoc.file.file_size)} mono /><DetailItem label="Provider" value={selectedDoc.file.storage_provider} mono /><DetailItem label="Uploaded" value={formatDateTime(selectedDoc.file.created_at)} mono /></div><div className="mobile-actions mt-3"><button className="btn btn-primary" onClick={() => openDocFileByDocument(selectedDoc, false)}>Open file</button><button className="btn btn-ghost" onClick={() => openDocFileByDocument(selectedDoc, true)}>Download</button></div></> : <p>No file has been uploaded for this document.</p>}</div>
                  {adminCanEditSelection && <div className="docs-admin-tools"><h3>Admin Tools</h3><label className="upload-zone docs-upload-zone"><input type="file" onChange={handleUploadFile} disabled={fileUploading} /><span>{fileUploading ? 'Uploading...' : 'Upload or replace file'}</span><small>PDF, images, certificates, manuals, and vendor documents</small></label><form onSubmit={handleAddReference} className="docs-reference-form"><div className="field"><label>Reference Type</label><select value={referenceForm.reference_type} onChange={(e) => setReferenceForm((current) => ({ ...current, reference_type: e.target.value }))}>{REFERENCE_TYPES.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></div><div className="field"><label>Reference Value</label><input value={referenceForm.reference_value} onChange={(e) => setReferenceForm((current) => ({ ...current, reference_value: e.target.value }))} placeholder="PN-12345, SN-9001, ITEM-77..." /></div><div className="field"><label>Label</label><input value={referenceForm.label} onChange={(e) => setReferenceForm((current) => ({ ...current, label: e.target.value }))} placeholder="Optional display label" /></div><button className="btn btn-ghost" disabled={saving || !referenceForm.reference_value.trim()}>Add reference</button></form></div>}
                </div>
              )}
            </aside>
          </div>
        </>
      )}
    </>
  )
}
