import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { api } from '../services/api'
import { Alert, Empty, Loading, Pagination } from '../components/ui'

const LIMIT = 50
const STATUSES = ['', 'open', 'assigned', 'in_progress', 'completed', 'cancelled']
const PRIORITIES = ['', 'low', 'medium', 'high', 'critical']

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

function toApiDateTime(value) {
  return value ? new Date(value).toISOString() : null
}

function makeEmptyForm() {
  return {
    title: '',
    description: '',
    priority: 'medium',
    status: 'open',
    asset_id: '',
    assigned_user_id: '',
    due_date: '',
  }
}

function WorkOrderStatusBadge({ status }) {
  return <span className={`badge wo-status-${status || 'unknown'}`}>{pretty(status)}</span>
}

function PriorityBadge({ priority }) {
  return <span className={`badge wo-priority-${priority || 'unknown'}`}>{pretty(priority)}</span>
}

export default function WorkOrdersPage() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [skip, setSkip] = useState(0)
  const [filters, setFilters] = useState({
    search: '',
    status: '',
    priority: '',
    assigned_user_id: '',
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [creating, setCreating] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState(() => makeEmptyForm())

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.getWorkOrders({
        skip,
        limit: LIMIT,
        search: filters.search.trim() || undefined,
        status: filters.status || undefined,
        priority: filters.priority || undefined,
        assigned_user_id: filters.assigned_user_id || undefined,
      })
      setItems(res.items || [])
      setTotal(res.total || 0)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [filters, skip])

  useEffect(() => { load() }, [load])
  useEffect(() => { setSkip(0) }, [filters.search, filters.status, filters.priority, filters.assigned_user_id])

  function setFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }))
  }

  function setFormValue(name, value) {
    setForm((current) => ({ ...current, [name]: value }))
  }

  async function createWorkOrder(e) {
    e.preventDefault()
    setCreating(true)
    setError(null)
    setSuccess(null)
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || null,
        priority: form.priority,
        status: form.status,
        asset_id: Number(form.asset_id),
        assigned_user_id: form.assigned_user_id ? Number(form.assigned_user_id) : null,
        due_date: toApiDateTime(form.due_date),
      }
      const created = await api.createWorkOrder(payload)
      setSuccess(`Work order ${created.code} created.`)
      setForm(makeEmptyForm())
      setFormOpen(false)
      await load()
      navigate(`/work-orders/${created.id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setCreating(false)
    }
  }

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">// WORK ORDERS</h1>
        {!loading && <span className="page-count">{total} records</span>}
        {isAdmin && (
          <button className="btn btn-primary" style={{ marginLeft: 'auto' }} onClick={() => setFormOpen((open) => !open)}>
            {formOpen ? 'Close' : '+ New Work Order'}
          </button>
        )}
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {success && <Alert type="success">{success}</Alert>}

      {isAdmin && formOpen && (
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">▣ Create Work Order</span>
          </div>
          <form className="panel-body wo-form" onSubmit={createWorkOrder}>
            <div className="field-row cols-3">
              <div className="field">
                <label>Title</label>
                <input required value={form.title} onChange={(e) => setFormValue('title', e.target.value)} placeholder="Inspect top drive encoder" />
              </div>
              <div className="field">
                <label>Asset ID</label>
                <input required type="number" min="1" value={form.asset_id} onChange={(e) => setFormValue('asset_id', e.target.value)} placeholder="42" />
              </div>
              <div className="field">
                <label>Assigned Technician ID</label>
                <input type="number" min="1" value={form.assigned_user_id} onChange={(e) => setFormValue('assigned_user_id', e.target.value)} placeholder="Optional" />
              </div>
            </div>
            <div className="field-row cols-3">
              <div className="field">
                <label>Priority</label>
                <select value={form.priority} onChange={(e) => setFormValue('priority', e.target.value)}>
                  {PRIORITIES.filter(Boolean).map((priority) => <option key={priority} value={priority}>{pretty(priority)}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Status</label>
                <select value={form.status} onChange={(e) => setFormValue('status', e.target.value)}>
                  {STATUSES.filter(Boolean).map((status) => <option key={status} value={status}>{pretty(status)}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Due Date</label>
                <input type="datetime-local" value={form.due_date} onChange={(e) => setFormValue('due_date', e.target.value)} />
              </div>
            </div>
            <div className="field">
              <label>Description</label>
              <textarea value={form.description} onChange={(e) => setFormValue('description', e.target.value)} placeholder="Scope, checks, constraints, safety notes..." />
            </div>
            <button className="btn btn-primary" disabled={creating}>
              {creating ? 'Creating...' : 'Create Work Order'}
            </button>
          </form>
        </div>
      )}

      <div className="panel">
        <div className="panel-header">
          <span className="panel-title">▤ Work Order Queue</span>
          <div className="search-bar wo-search">
            <input value={filters.search} onChange={(e) => setFilter('search', e.target.value)} placeholder="Search code, title, description..." />
            <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
              {STATUSES.map((status) => <option value={status} key={status || 'all'}>{status ? pretty(status) : 'All statuses'}</option>)}
            </select>
            <select value={filters.priority} onChange={(e) => setFilter('priority', e.target.value)}>
              {PRIORITIES.map((priority) => <option value={priority} key={priority || 'all'}>{priority ? pretty(priority) : 'All priorities'}</option>)}
            </select>
            <input type="number" min="1" value={filters.assigned_user_id} onChange={(e) => setFilter('assigned_user_id', e.target.value)} placeholder="Tech ID" />
            <button className="btn btn-ghost btn-sm" onClick={load}>↺</button>
          </div>
        </div>

        <div className="table-wrap">
          {loading ? <Loading label="Loading work orders..." /> : items.length === 0 ? (
            <Empty icon="▣" message="No work orders found" />
          ) : (
            <table className="responsive-table">
              <thead>
                <tr>
                  <th>WO Code</th>
                  <th>Title</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Asset</th>
                  <th>Assigned</th>
                  <th>Due</th>
                  <th>Created</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {items.map((wo) => (
                  <tr key={wo.id}>
                    <td data-label="WO Code" className="mono docs-code">{wo.code}</td>
                    <td data-label="Title" style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{wo.title}</td>
                    <td data-label="Priority"><PriorityBadge priority={wo.priority} /></td>
                    <td data-label="Status"><WorkOrderStatusBadge status={wo.status} /></td>
                    <td data-label="Asset" className="mono">{wo.asset_id}</td>
                    <td data-label="Assigned" className="mono">{wo.assigned_user_id || '—'}</td>
                    <td data-label="Due" className="mono text-muted">{formatDateTime(wo.due_date)}</td>
                    <td data-label="Created" className="mono text-muted">{formatDateTime(wo.created_at)}</td>
                    <td data-label="Action"><Link className="btn btn-ghost btn-sm" to={`/work-orders/${wo.id}`}>Open</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {!loading && (
          <div style={{ padding: '0 18px 14px' }}>
            <Pagination skip={skip} limit={LIMIT} total={total} onSkip={setSkip} />
          </div>
        )}
      </div>
    </>
  )
}
