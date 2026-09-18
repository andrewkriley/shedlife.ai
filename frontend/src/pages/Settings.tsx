import { useEffect, useState } from 'react'
import { getLiveModels, getSubAgentSettings, setModelAssignments } from '../lib/api'
import type { SubAgentSetting } from '../lib/api'

export function Settings({ onClose }: { onClose: () => void }) {
  const [subAgents, setSubAgents] = useState<SubAgentSetting[]>([])
  const [liveModels, setLiveModels] = useState<Record<string, string[]>>({})
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  useEffect(() => {
    getSubAgentSettings().then(setSubAgents).catch(() => setStatus('Failed to load sub-agents.'))
    getLiveModels()
      .then((models) => {
        setLiveModels(models)
        const firstProvider = Object.keys(models)[0]
        if (firstProvider) {
          setProvider(firstProvider)
          setModel(models[firstProvider][0] ?? '')
        }
      })
      .catch(() => setStatus('Failed to load live models.'))
  }, [])

  function toggleSelected(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function handleProviderChange(next: string) {
    setProvider(next)
    setModel(liveModels[next]?.[0] ?? '')
  }

  async function handleApply() {
    if (selectedIds.size === 0 || !provider || !model) return
    setStatus(null)
    try {
      const updated = await setModelAssignments(Array.from(selectedIds), provider, model)
      setSubAgents(updated)
      setStatus('Assignment applied.')
    } catch {
      setStatus('Failed to apply assignment.')
    }
  }

  async function handleClear() {
    if (selectedIds.size === 0) return
    setStatus(null)
    try {
      const updated = await setModelAssignments(Array.from(selectedIds), null, null)
      setSubAgents(updated)
      setStatus('Override cleared.')
    } catch {
      setStatus('Failed to clear override.')
    }
  }

  return (
    <div>
      <h1>Settings</h1>
      <button type="button" onClick={onClose}>
        Back to chat
      </button>

      <h2>Sub-agents</h2>
      <ul aria-label="sub-agents">
        {subAgents.map((sa) => (
          <li key={sa.id}>
            <label>
              <input
                type="checkbox"
                checked={selectedIds.has(sa.id)}
                onChange={() => toggleSelected(sa.id)}
              />
              {sa.id} — {sa.provider}/{sa.model}
              {sa.overridden ? ' (override)' : ' (default)'}
            </label>
          </li>
        ))}
      </ul>

      <h2>Assign model</h2>
      <label htmlFor="provider">Provider</label>
      <select id="provider" value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
        {Object.keys(liveModels).map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <label htmlFor="model">Model</label>
      <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
        {(liveModels[provider] ?? []).map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>

      <button type="button" onClick={handleApply} disabled={selectedIds.size === 0}>
        Apply to selected
      </button>
      <button type="button" onClick={handleClear} disabled={selectedIds.size === 0}>
        Clear override
      </button>

      {status && <p role="status">{status}</p>}
    </div>
  )
}
