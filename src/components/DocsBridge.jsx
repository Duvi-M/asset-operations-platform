import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'

const PACKET_CATEGORIES = [
  {
    key: 'manuals',
    label: 'Manuals',
    match: ['manual', 'service_manual', 'operation_manual', 'maintenance_manual'],
  },
  {
    key: 'procedures',
    label: 'Procedures',
    match: ['procedure', 'work_instruction', 'sop', 'installation', 'maintenance'],
  },
  {
    key: 'certificates',
    label: 'Certificates',
    match: ['certificate', 'certification', 'calibration', 'compliance'],
  },
  {
    key: 'diagrams',
    label: 'Diagrams / Drawings',
    match: ['drawing', 'diagram', 'schematic', 'blueprint'],
  },
  {
    key: 'datasheets',
    label: 'Datasheets',
    match: ['datasheet', 'data_sheet', 'ficha_tecnica', 'technical_sheet'],
  },
  {
    key: 'reports',
    label: 'Reports',
    match: ['report', 'inspection_report', 'test_report', 'field_report'],
  },
  {
    key: 'related',
    label: 'Related',
    match: [],
  },
]

function uniqueDocs(items) {
  const seen = new Set()
  return items.filter((doc) => {
    if (!doc?.id || seen.has(doc.id)) return false
    seen.add(doc.id)
    return true
  })
}

export function getAssetDocsReferences(asset) {
  if (!asset) return []

  return [
    { type: 'part_number', label: 'Part Number', value: asset.part?.part_number },
    { type: 'serial_number', label: 'Serial', value: asset.serial_number },
    { type: 'internal_code', label: 'Internal Code', value: asset.internal_code },
    { type: 'asset_id', label: 'Asset ID', value: asset.id ? String(asset.id) : '' },
    { type: 'part_id', label: 'Part ID', value: asset.part_id ? String(asset.part_id) : '' },
  ].filter((ref) => ref.value)
}

export function getAssetDocsQuery(asset) {
  const refs = getAssetDocsReferences(asset)
  return refs[0]?.value || asset?.item_name || ''
}

export function docsPortalPathForAsset(asset) {
  const query = getAssetDocsQuery(asset)
  return query ? `/docs-portal?q=${encodeURIComponent(query)}` : '/docs-portal'
}

function docsPortalPathForItem(item) {
  const value = item?.item_id || item?.part_number || item?.id
  return value ? `/docs-portal?item_id=${encodeURIComponent(value)}` : '/docs-portal'
}

function cleanParams(params) {
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value != null && value !== ''))
}

function getAssetResolveParams(asset) {
  if (!asset) return {}

  return cleanParams({
    asset_id: asset.id,
    part_number: asset.part?.part_number || asset.part_number,
    serial_number: asset.serial_number,
    internal_code: asset.internal_code,
    item_id: asset.item_id || asset.part?.item_id,
    model: asset.model || asset.part?.model,
  })
}

function isExpired(doc) {
  if (!doc?.expires_at) return false
  return new Date(doc.expires_at).getTime() < Date.now()
}

function docStatus(doc) {
  if (isExpired(doc)) return 'expired'
  return doc?.status || 'unknown'
}

function categoryForDoc(doc) {
  const type = String(doc?.document_type || '').toLowerCase()
  return PACKET_CATEGORIES.find((category) => (
    category.match.some((token) => type.includes(token))
  )) || PACKET_CATEGORIES.find((category) => category.key === 'related')
}

function compareDocs(a, b) {
  const aActive = a.status === 'active' && !isExpired(a)
  const bActive = b.status === 'active' && !isExpired(b)
  if (aActive !== bActive) return aActive ? -1 : 1

  const aUpdated = new Date(a.updated_at || a.effective_date || 0).getTime()
  const bUpdated = new Date(b.updated_at || b.effective_date || 0).getTime()
  return bUpdated - aUpdated
}

function packetGroups(docs) {
  const groups = PACKET_CATEGORIES.map((category) => ({
    ...category,
    docs: [],
    featuredId: null,
  }))

  docs.forEach((doc) => {
    const category = categoryForDoc(doc)
    groups.find((group) => group.key === category.key)?.docs.push(doc)
  })

  return groups.map((group) => {
    const sortedDocs = [...group.docs].sort(compareDocs)
    const featured = sortedDocs.find((doc) => doc.status === 'active' && !isExpired(doc)) || null
    return { ...group, docs: sortedDocs, featuredId: featured?.id || null }
  })
}

function prettyType(value) {
  return String(value || 'Document').replaceAll('_', ' ')
}

function prettyMatch(value) {
  return String(value || '').replaceAll('_', ' ')
}

function warningTitle(type) {
  const labels = {
    missing_file: 'Missing file',
    obsolete_document: 'Obsolete',
    expired_certificate: 'Expired certificate',
    draft_document: 'Draft',
    no_documents: 'No documents',
  }
  return labels[type] || prettyMatch(type)
}

function flattenPacketDocuments(packet) {
  const groups = packet?.documents || {}
  return uniqueDocs(Object.values(groups).flatMap((docs) => docs || []))
}

function officialPacketGroups(packet) {
  const documents = packet?.documents || {}
  const warnings = packet?.warnings || []

  return PACKET_CATEGORIES.map((category) => {
    const docs = [...(documents[category.key] || [])].sort(compareDocs)
    const featured = docs.find((doc) => doc.status === 'active' && !isExpired(doc)) || null
    return {
      ...category,
      docs,
      featuredId: featured?.id || null,
      warningCount: warnings.filter((warning) => docs.some((doc) => doc.id === warning.document_id)).length,
    }
  })
}

async function loadDocsForAsset(asset, limit = 20) {
  const refs = getAssetDocsReferences(asset)
  if (!refs.length) return []

  const responses = await Promise.allSettled(
    refs.map((ref) => api.searchDocs({
      reference_type: ref.type,
      reference_value: ref.value,
      limit,
    }))
  )

  const slimDocs = uniqueDocs(responses.flatMap((result) => (
    result.status === 'fulfilled' ? result.value.items || [] : []
  ))).slice(0, limit)

  const details = await Promise.allSettled(slimDocs.map((doc) => api.getDoc(doc.id)))
  return slimDocs.map((doc, index) => (
    details[index].status === 'fulfilled' ? details[index].value : doc
  ))
}

function PacketStatusBadge({ doc }) {
  const status = docStatus(doc)
  return (
    <span className={`badge docs-status-${status}`}>
      {status === 'expired' ? 'Expired' : status}
    </span>
  )
}

export function DocsBridgePanel({ asset, title = 'Technical Packet', compact = false, limit = 20 }) {
  const [docs, setDocs] = useState([])
  const [resolvedMatch, setResolvedMatch] = useState(null)
  const [packet, setPacket] = useState(null)
  const [usingFallback, setUsingFallback] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const refs = useMemo(() => getAssetDocsReferences(asset), [asset])
  const resolvedItem = resolvedMatch?.technical_item || null
  const portalPath = resolvedItem ? docsPortalPathForItem(resolvedItem) : docsPortalPathForAsset(asset)
  const groups = useMemo(() => (
    packet ? officialPacketGroups(packet) : packetGroups(docs)
  ), [docs, packet])
  const packetWarnings = packet?.warnings || []

  useEffect(() => {
    let alive = true

    async function load() {
      if (!asset || refs.length === 0) {
        setDocs([])
        setResolvedMatch(null)
        setPacket(null)
        setUsingFallback(false)
        return
      }

      setLoading(true)
      setError(null)
      setResolvedMatch(null)
      setPacket(null)
      setUsingFallback(false)
      try {
        let match = null
        try {
          const resolved = await api.resolveTechnicalItems({ ...getAssetResolveParams(asset), limit: 5 })
          match = resolved.items?.[0] || null
        } catch {
          match = null
        }

        if (match?.technical_item?.id) {
          const officialPacket = await api.getTechnicalItemPacket(match.technical_item.id)
          if (!alive) return
          setResolvedMatch(match)
          setPacket(officialPacket)
          setDocs(flattenPacketDocuments(officialPacket))
          return
        }

        const items = await loadDocsForAsset(asset, limit)
        if (alive) {
          setDocs(items)
          setUsingFallback(true)
        }
      } catch (err) {
        if (alive) setError(err.message)
      } finally {
        if (alive) setLoading(false)
      }
    }

    load()
    return () => { alive = false }
  }, [asset, limit, refs])

  if (!asset) return null

  return (
    <div className={compact ? 'docs-bridge docs-bridge-compact' : 'docs-bridge'}>
      <div className="docs-bridge-header">
        <div>
          <span className="panel-title">{title}</span>
          <p className="helper-text">
            SGOI Core resolves this asset through the external Docs service before showing documents.
          </p>
        </div>
        <Link className="btn btn-ghost btn-sm" to={portalPath}>
          {resolvedItem ? 'Open Technical Packet' : 'Open in SGOI Docs'}
        </Link>
      </div>

      {resolvedItem && (
        <div className="resolved-technical-item">
          <div className="resolved-technical-item-head">
            <div>
              <span className="panel-title">Resolved Technical Item</span>
              <strong>{resolvedItem.name}</strong>
            </div>
            <span className="badge docs-status-active">{resolvedMatch.confidence}% match</span>
          </div>
          <div className="resolved-technical-item-grid">
            <span><em>Part Number</em><strong>{resolvedItem.part_number || '—'}</strong></span>
            <span><em>Item ID</em><strong>{resolvedItem.item_id || '—'}</strong></span>
            <span><em>Model</em><strong>{resolvedItem.model || '—'}</strong></span>
            <span><em>Manufacturer</em><strong>{resolvedItem.manufacturer || '—'}</strong></span>
            <span><em>Matched On</em><strong>{resolvedMatch.matched_on?.map(prettyMatch).join(', ') || '—'}</strong></span>
          </div>
        </div>
      )}

      <div className="docs-bridge-refs">
        {refs.map((ref) => (
          <span className="docs-chip" key={`${ref.type}:${ref.value}`}>
            <strong>{ref.label}</strong>
            <span>{ref.value}</span>
          </span>
        ))}
      </div>

      {error && <div className="alert alert-error mt-3">{error}</div>}
      {usingFallback && (
        <div className="alert alert-info">
          No catalog item resolved. Showing legacy document-search packet from asset references.
        </div>
      )}
      {packetWarnings.length > 0 && (
        <div className="packet-warning-list">
          {packetWarnings.map((warning, index) => (
            <div className={`packet-warning packet-warning-${warning.type}`} key={`${warning.type}:${warning.document_id || index}`}>
              <strong>{warningTitle(warning.type)}</strong>
              <span>{warning.document_code ? `${warning.document_code}: ` : ''}{warning.message}</span>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <div className="docs-bridge-state">Building technical packet...</div>
      ) : docs.length ? (
        <div className="technical-packet-grid">
          {groups.map((group) => (
            <section className="packet-category" key={group.key}>
              <div className="packet-category-head">
                <span>{group.label}</span>
                <strong>{group.docs.length}</strong>
              </div>
              {group.docs.length ? (
                <div className="packet-doc-list">
                  {group.docs.map((doc) => {
                    const featured = doc.id === group.featuredId
                    const docWarnings = packetWarnings.filter((warning) => warning.document_id === doc.id)
                    return (
                      <Link
                        className={`packet-doc${featured ? ' packet-doc-featured' : ''}`}
                        to={`/docs-portal?q=${encodeURIComponent(doc.document_code)}`}
                        key={doc.id}
                      >
                        <div className="packet-doc-topline">
                          <span className="mono docs-code">{doc.document_code}</span>
                          <PacketStatusBadge doc={doc} />
                        </div>
                        <strong>{doc.title}</strong>
                        <div className="packet-doc-meta">
                          <span>{prettyType(doc.document_type)}</span>
                          <span>Rev {doc.revision || '—'}</span>
                          {!doc.file && <span>Missing file</span>}
                          {docWarnings.map((warning) => <span key={warning.type}>{warningTitle(warning.type)}</span>)}
                          {featured && <em>Recommended</em>}
                        </div>
                      </Link>
                    )
                  })}
                </div>
              ) : (
                <div className="packet-empty">No document indexed</div>
              )}
            </section>
          ))}
        </div>
      ) : (
        <div className="docs-bridge-state">No documents found for these references.</div>
      )}
    </div>
  )
}

export function DocsAvailability({ asset }) {
  const [count, setCount] = useState(null)
  const [resolved, setResolved] = useState(false)
  const [loading, setLoading] = useState(false)
  const portalPath = docsPortalPathForAsset(asset)

  useEffect(() => {
    let alive = true

    async function load() {
      setLoading(true)
      try {
        let match = null
        try {
          const resolvedItems = await api.resolveTechnicalItems({ ...getAssetResolveParams(asset), limit: 1 })
          match = resolvedItems.items?.[0] || null
        } catch {
          match = null
        }

        if (match?.technical_item?.id) {
          const packet = await api.getTechnicalItemPacket(match.technical_item.id)
          if (alive) {
            setResolved(true)
            setCount(flattenPacketDocuments(packet).length)
          }
          return
        }

        const items = await loadDocsForAsset(asset, 12)
        if (alive) {
          setResolved(false)
          setCount(items.length)
        }
      } catch {
        if (alive) {
          setResolved(false)
          setCount(0)
        }
      } finally {
        if (alive) setLoading(false)
      }
    }

    load()
    return () => { alive = false }
  }, [asset])

  return (
    <div className="docs-availability">
      <span className={`badge ${count > 0 ? 'docs-status-active' : 'badge-unknown'}`}>
        {loading ? 'Checking' : count > 0 ? `${count} ${resolved ? 'packet docs' : 'docs'}` : 'No docs'}
      </span>
      <Link className="btn btn-ghost btn-sm" to={portalPath}>
        SGOI Docs
      </Link>
    </div>
  )
}
