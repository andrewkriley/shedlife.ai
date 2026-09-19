import { useEffect, useState } from 'react'
import { fileIssue, getIssues, type LocalIssue } from '../lib/api'

export function IssuesPanel() {
  const [issues, setIssues] = useState<LocalIssue[]>([])
  const [summary, setSummary] = useState('')
  const [detail, setDetail] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  async function refresh() {
    setIssues(await getIssues())
  }

  useEffect(() => {
    refresh().catch(() => setStatus('Failed to load issues.'))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setStatus(null)
    try {
      await fileIssue({ summary, detail })
      setSummary('')
      setDetail('')
      await refresh()
      setStatus('Filed.')
    } catch {
      setStatus('Failed to file issue.')
    }
  }

  return (
    <section className="panel" aria-label="issues">
      <h2>Issues</h2>
      <ul aria-label="issue-list">
        {issues.map((issue) => (
          <li key={issue.id}>
            <strong>{issue.classification}</strong> — {issue.summary}
          </li>
        ))}
      </ul>
      <form onSubmit={handleSubmit}>
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
        <button type="submit">File issue</button>
      </form>
      {status && <p role="status">{status}</p>}
    </section>
  )
}
