// src/components/TaskModal.jsx
import { useState, useEffect } from 'react'

const EMPTY = { title: '', description: '', status: 'todo', priority: 2, due_date: '', tags: '' }

export default function TaskModal({ task, onSave, onClose }) {
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (task) {
      setForm({
        title: task.title || '',
        description: task.description || '',
        status: task.status || 'todo',
        priority: task.priority ?? 2,
        due_date: task.due_date ? task.due_date.slice(0, 16) : '',
        tags: task.tags || '',
      })
    } else {
      setForm(EMPTY)
    }
  }, [task])

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = {
        ...form,
        priority: Number(form.priority),
        due_date: form.due_date ? new Date(form.due_date).toISOString() : null,
        tags: form.tags || null,
        description: form.description || null,
      }
      await onSave(payload)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function set(field) {
    return (e) => setForm(f => ({ ...f, [field]: e.target.value }))
  }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <div className="modal-title">{task ? 'Edit Task' : 'New Task'}</div>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Title *</label>
            <input className="form-control" value={form.title} onChange={set('title')} required placeholder="Task title" />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea className="form-control" value={form.description} onChange={set('description')} placeholder="Optional details..." />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div className="form-group">
              <label className="form-label">Status</label>
              <select className="form-control" value={form.status} onChange={set('status')}>
                <option value="todo">Todo</option>
                <option value="in_progress">In Progress</option>
                <option value="done">Done</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Priority</label>
              <select className="form-control" value={form.priority} onChange={set('priority')}>
                <option value={1}>Low</option>
                <option value={2}>Medium</option>
                <option value={3}>High</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Due Date</label>
            <input className="form-control" type="datetime-local" value={form.due_date} onChange={set('due_date')} />
          </div>

          <div className="form-group">
            <label className="form-label">Tags (comma-separated)</label>
            <input className="form-control" value={form.tags} onChange={set('tags')} placeholder="e.g. frontend, urgent" />
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? <span className="spinner" /> : (task ? 'Save changes' : 'Create task')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
