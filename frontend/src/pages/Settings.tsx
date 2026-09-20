import { useEffect, useState } from 'react'
import { AssistantStatus } from '../components/AssistantStatus'
import { getLiveModels, getSubAgentSettings, setModelAssignments, setProviderKey } from '../lib/api'
import type { SubAgentSetting } from '../lib/api'

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
]

export function Settings({ onClose: _onClose }: { onClose: () => void }) {
  const [subAgents, setSubAgents] = useState<SubAgentSetting[]>([])
  const [liveModels, setLiveModels] = useState<Record<string, string[]>>({})
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [provider, setProvider] = useState('anthropic')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [busy, setBusy] = useState<'apply' | 'clear' | 'key' | null>(null)

  useEffect(() => {
    getSubAgentSettings()
      .then((agents) => {
        setSubAgents(agents)
        if (agents.length === 1) setSelectedIds(new Set([agents[0].id]))
      })
      .catch(() => setStatus('Failed to load sub-agents.'))
    getLiveModels()
      .then((models) => {
        setLiveModels(models)
        const firstProvider = Object.keys(models).includes('openai')
          ? 'openai'
          : Object.keys(models)[0]
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

  async function handleSaveKey() {
    if (!apiKey.trim()) {
      setStatus('Paste an API key for the selected provider.')
      return
    }
    setBusy('key')
    setStatus('Saving…')
    try {
      await setProviderKey(provider, apiKey.trim())
      setApiKey('')
      const models = await getLiveModels()
      setLiveModels(models)
      setModel(models[provider]?.[0] ?? '')
      setStatus(`Saved the ${provider} key. Chat will use this provider.`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to save the provider key.')
    } finally {
      setBusy(null)
    }
  }

  async function handleApply() {
    if (selectedIds.size === 0 || !provider || !model) {
      setStatus('Select an assistant, then choose a provider and model.')
      return
    }
    setBusy('apply')
    setStatus('Applying…')
    try {
      const updated = await setModelAssignments(Array.from(selectedIds), provider, model)
      setSubAgents(updated)
      setStatus('This model is now assigned to the selected assistant.')
    } catch {
      setStatus('Failed to apply assignment.')
    } finally {
      setBusy(null)
    }
  }

  async function handleClear() {
    if (selectedIds.size === 0) {
      setStatus('Select an assistant first.')
      return
    }
    setBusy('clear')
    setStatus('Resetting…')
    try {
      const updated = await setModelAssignments(Array.from(selectedIds), null, null)
      setSubAgents(updated)
      setStatus('The selected assistant is back on its default model.')
    } catch {
      setStatus('Failed to clear override.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="settings-page">
      <p className="lede">
        Choose which assistant you are talking to, then pick the model it should use.
        A lone assistant is already selected.
      </p>

      <fieldset className="group">
        <legend>Connection</legend>
        <AssistantStatus />
        <p className="hint">Change the provider key without re-running setup.</p>
        <div className="field-grid">
          <div>
            <label htmlFor="connection-provider">Provider</label>
            <select
              id="connection-provider"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {PROVIDERS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="connection-key">API key</label>
            <input
              id="connection-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste a new key to switch provider"
              autoComplete="off"
            />
          </div>
        </div>
        <div className="panel-actions">
          <button type="button" onClick={() => void handleSaveKey()} disabled={busy !== null}>
            {busy === 'key' ? 'Saving…' : 'Save provider key'}
          </button>
        </div>
      </fieldset>

      <fieldset className="group">
        <legend>Your assistants</legend>
        <ul aria-label="sub-agents" className="assistant-cards">
          {subAgents.map((sa) => (
            <li key={sa.id} className={selectedIds.has(sa.id) ? 'is-selected' : undefined}>
              <label>
                <input
                  type="checkbox"
                  checked={selectedIds.has(sa.id)}
                  onChange={() => toggleSelected(sa.id)}
                />
                <span>
                  <strong>{sa.id}</strong>
                  <span className="assistant-cards__meta">
                    {sa.provider}/{sa.model}
                  </span>
                  <span className="assistant-cards__meta">
                    {sa.overridden ? 'Custom model' : 'Using the default model'}
                  </span>
                  {sa.description && <span className="assistant-cards__desc">{sa.description}</span>}
                </span>
              </label>
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset className="group">
        <legend>Change the model</legend>
        <p className="hint">This is the model the assistant uses to talk with you.</p>
        <div className="field-grid">
          <div>
            <label htmlFor="provider">Provider</label>
            <select
              id="provider"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
            >
              {PROVIDERS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="model">Model</label>
            <select id="model" value={model} onChange={(e) => setModel(e.target.value)}>
              {(liveModels[provider] ?? []).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="panel-actions">
          <button type="button" onClick={handleApply} disabled={selectedIds.size === 0 || busy !== null}>
            {busy === 'apply' ? 'Applying…' : 'Apply this model'}
          </button>
          <button
            type="button"
            className="button-secondary"
            onClick={handleClear}
            disabled={selectedIds.size === 0 || busy !== null}
          >
            {busy === 'clear' ? 'Resetting…' : 'Use default model'}
          </button>
        </div>
      </fieldset>

      {status && <p role="status">{status}</p>}
    </div>
  )
}
