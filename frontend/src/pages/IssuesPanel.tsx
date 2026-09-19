import { useEffect, useState } from 'react'
import { fileIssue, getIssues, type LocalIssue } from '../lib/api'

export function IssuesPanel() {
  const [issues, setIssues] = useState<LocalIssue[]>([])
  const [summary, setSummary] = useState('')
  const [detail, setDetail] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function refresh() {
    setIssues(await getIssues())
  }

  useEffect(() => {
    refresh().catch(() => setStatus('Failed to load issues.'))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setStatus('Filing…')
    try {
      await fileIssue({ summary, detail })
      setSummary('')
      setDetail('')
      await refresh()
      setStatus('Filed.')
    } catch {
      setStatus('Failed to file issue.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel" aria-label="issues">
      <fieldset className="group">
        <legend>Open issues</legend>
        <ul aria-label="issue-list" className="issue-list">
          {issues.length === 0 && <li className="empty-hint">No issues yet.</li>}
          {issues.map((issue) => (
            <li key={issue.id}>
              <strong>{issue.classification}</strong> — {issue.summary}
            </li>
          ))}
        </ul>
      </fieldset>
      <form onSubmit={handleSubmit}>
        <fieldset className="group">
          <legend>File an issue</legend>
          <label htmlFor="issue-summary">Summary</label>
          <input
            id="issue-summary"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            required
          />
          <label htmlFor="issue-detail">Detail</label>
          <textarea
            id="issue-detail"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            required
          />
          <div className="panel-actions">
            <button type="submit" disabled={busy}>
              {busy ? 'Filing…' : 'File issue'}
            </button>
          </div>
        </fieldset>
      </form>
      {status && <p role="status">{status}</p>}
    </section>
  )
}
