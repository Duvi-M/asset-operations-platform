import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DocsBridgePanel } from '../components/DocsBridge'
import { Alert, Empty, Loading } from '../components/ui'
import { api } from '../services/api'

const STATUSES = ['open', 'assigned', 'in_progress', 'completed', 'cancelled']
const PRIORITIES = ['low', 'medium', 'high', 'critical']

function pretty(value) {
  if (!value) return '—'
  return String(value).replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
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

function toDateTimeLocal(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

function toApiDateTime(value) {
  return value ? new Date(value).toISOString() : null
}

function WorkOrderStatusBadge({ status }) {
  return <span className={`badge wo-status-${status || 'unknown'}`}>{pretty(status)}</span>
}

function PriorityBadge({ priority }) {
  return <span className={`badge wo-priority-${priority || 'unknown'}`}>{pretty(priority)}</span>
}

function DetailItem({ label, value, mono = false }) {
  return (
    <div className="docs-detail-item">
      <span>{label}</span>
      <strong className={mono ? 'mono' : ''}>{value || '—'}</strong>
    </div>
  )
}

function makeForm(wo) {
  return {
    title: wo.title || '',
    description: wo.description || '',
    priority: wo.priority || 'medium',
    status: wo.status || 'open',
    asset_id: wo.asset_id ? String(wo.asset_id) : '',
    assigned_user_id: wo.assigned_user_id ? String(wo.assigned_user_id) : '',
    due_date: toDateTimeLocal(wo.due_date),
  }
}

export default function WorkOrderDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [workOrder, setWorkOrder] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.getWorkOrder(id)
      setWorkOrder(res)
      setForm(makeForm(res))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => { load() }, [load])

  const linkedAsset = useMemo(() => {
    if (!workOrder?.asset) return null
    return {
      ...workOrder.asset,
      part_id: workOrder.asset.part_id || workOrder.asset_id,
    }
  }, [workOrder])

  function setFormValue(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        priority: form.priority,
        status: form.status,
        asset_id: form.asset_id ? Number(form.asset_id) : null,
        assigned_user_id: form.assigned_user_id ? Number(form.assigned_user_id) : null,
        due_date: toApiDateTime(form.due_date),
      }
      const updated = await api.updateWorkOrder(id, payload)
      setWorkOrder(updated)
      setForm(makeForm(updated))
      setEditing(false)
      setSuccess('Work order updated.')
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus(status) {
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const updated = await api.updateWorkOrder(id, { status })
      setWorkOrder(updated)
      setForm(makeForm(updated))
      setSuccess(`Status changed to ${pretty(status)}.`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading label="Loading work order..." />
  if (error && !workOrder) return <Alert type="error">{error}</Alert>
  if (!workOrder) return null

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// {workOrder.code}</h1>
        <PriorityBadge priority={workOrder.priority} />
        <WorkOrderStatusBadge status={workOrder.status} />
        <div className="mobile-actions" style={{ marginLeft: 'auto', justifyContent: 'flex-end' }}>
          <button className="btn btn-ghost" onClick={() => navigate('/work-orders')}>← Back</button>
          {isAdmin && <button className="btn btn-primary" onClick={() => setEditing((open) => !open)}>{editing ? 'Close Edit' : 'Edit'}</button>}
        </div>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {isAdmin && editing && form && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">▣ Edit Work Order</span>
          </div>
          <form className="panel-body wo-form" onSubmit={save}>
            <div className="field-row cols-3">
              <div className="field">
                <label>Title</label>
                <input required value={form.title} onChange={(e) => setFormValue('title', e.target.value)} />
              </div>
              <div className="field">
                <label>Asset ID</label>
                <input required type="number" min="1" value={form.asset_id} onChange={(e) => setFormValue('asset_id', e.target.value)} />
              </div>
              <div className="field">
                <label>Assigned Technician ID</label>
                <input type="number" min="1" value={form.assigned_user_id} onChange={(e) => setFormValue('assigned_user_id', e.target.value)} />
              </div>
            </div>
            <div className="field-row cols-3">
              <div className="field">
                <label>Priority</label>
                <select value={form.priority} onChange={(e) => setFormValue('priority', e.target.value)}>
                  {PRIORITIES.map((priority) => <option key={priority} value={priority}>{pretty(priority)}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Status</label>
                <select value={form.status} onChange={(e) => setFormValue('status', e.target.value)}>
                  {STATUSES.map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Due Date</label>
                <input type="datetime-local" value={form.due_date} onChange={(e) => setFormValue('due_date', e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Description</label>
              <textarea value={form.description} onChange={(e) => setFormValue('description', e.target.value)} />
            </div>
            <button className="btn btn-primary" disabled={saving}>{saving ? 'Saving...' : 'Save changes'}</button>
          </form>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▣ Work Order Detail</span>
          {isAdmin && (
            <div className="wo-status-actions">
              {STATUSES.map((status) => (
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={saving || status === workOrder.status}
                  key={status}
                  onClick={() => changeStatus(status)}
                >
                  {pretty(status)}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="panel-body">
          <div className="detail-grid">
            <DetailItem label="WO Code" value={workOrder.code} mono />
            <DetailItem label="Title" value={workOrder.title} />
            <DetailItem label="Asset" value={workOrder.asset?.item_name || `Asset #${workOrder.asset_id}`} />
            <DetailItem label="Assigned Technician" value={workOrder.assigned_user?.full_name || (workOrder.assigned_user_id ? `User #${workOrder.assigned_user_id}` : 'Unassigned')} />
            <DetailItem label="Creator" value={workOrder.creator?.full_name || (workOrder.created_by ? `User #${workOrder.created_by}` : '—')} />
            <DetailItem label="Priority" value={pretty(workOrder.priority)} />
            <DetailItem label="Status" value={pretty(workOrder.status)} />
            <DetailItem label="Due Date" value={formatDateTime(workOrder.due_date)} mono />
            <DetailItem label="Created Date" value={formatDateTime(workOrder.created_at)} mono />
          </div>
          <div className="docs-section mt-4">
            <h3>Description</h3>
            <p>{workOrder.description || 'No description recorded.'}</p>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">⬒ Linked Interventions</span>
        </div>
        <div className="panel-body">
          {workOrder.interventions?.length ? (
            <div className="wo-intervention-list">
              {workOrder.interventions.map((intervention) => (
                <Link className="docs-related" to={`/interventions/${intervention.id}`} key={intervention.id}>
                  <span>{pretty(intervention.type)}</span>
                  <strong>Intervention #{intervention.id}</strong>
                  <em>{intervention.technician} · {formatDateTime(intervention.created_at)}</em>
                </Link>
              ))}
            </div>
          ) : (
            <Empty icon="⬒" message="No interventions linked yet" />
          )}
        </div>
      </div>

      {linkedAsset && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">▧ Linked Asset Technical Packet</span>
            <span className="helper-text">{linkedAsset.item_name}</span>
          </div>
          <div className="panel-body">
            <DocsBridgePanel asset={linkedAsset} compact />
          </div>
        </div>
      )}
    </>
  )
}
