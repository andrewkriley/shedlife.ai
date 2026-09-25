import { useEffect, useState } from 'react'
import { AssistantStatus } from '../components/AssistantStatus'
import {
  getConnection,
  getLiveModels,
  getSubAgentSettings,
  notifyConnectionChanged,
  setModelAssignments,
  setProviderKey,
} from '../lib/api'
import type { SubAgentSetting } from '../lib/api'
import { FoundationsPanel } from './FoundationsPanel'

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
]

export function Settings({ onClose: _onClose }: { onClose: () => void }) {
  const [subAgents, setSubAgents] = useState<SubAgentSetting[]>([])
  const [liveModels, setLiveModels] = useState<Record<string, string[]>>({})
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [keyProvider, setKeyProvider] = useState('openai')
  const [liveVendor, setLiveVendor] = useState<string | null>(null)
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [busy, setBusy] = useState<'apply' | 'clear' | 'key' | null>(null)

  function pickModelForVendor(
    models: Record<string, string[]>,
    vendor: string | null,
    preferred?: string | null,
  ) {
    if (!vendor) {
      setModel('')
      return
    }
    const options = models[vendor] ?? []
    if (preferred && options.includes(preferred)) {
      setModel(preferred)
      return
    }
    setModel(options[0] ?? '')
  }

  useEffect(() => {
    getSubAgentSettings()
      .then((agents) => {
        setSubAgents(agents)
        if (agents.length === 1) setSelectedIds(new Set([agents[0].id]))
      })
      .catch(() => setStatus('Failed to load sub-agents.'))
    Promise.all([getLiveModels(), getConnection().catch(() => null)])
      .then(([models, connection]) => {
        setLiveModels(models)
        const vendor = connection?.configured ? connection.provider : null
        setLiveVendor(vendor)
        const keyDefault =
          vendor ?? (Object.keys(models).includes('openai') ? 'openai' : Object.keys(models)[0])
        if (keyDefault) setKeyProvider(keyDefault)
        pickModelForVendor(models, vendor, connection?.model)
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

  function handleKeyProviderChange(next: string) {
    setKeyProvider(next)
  }

  async function handleSaveKey() {
    if (!apiKey.trim()) {
      setStatus('Paste an API key for the selected provider.')
      return
    }
    setBusy('key')
    setStatus('Saving…')
    try {
      await setProviderKey(keyProvider, apiKey.trim())
      setApiKey('')
      const [models, connection] = await Promise.all([
        getLiveModels(),
        getConnection().catch(() => null),
      ])
      setLiveModels(models)
      const vendor = connection?.configured ? connection.provider : keyProvider
      setLiveVendor(vendor)
      pickModelForVendor(models, vendor, connection?.model)
      notifyConnectionChanged()
      setStatus(`Saved the ${keyProvider} key. Chat will use this provider.`)
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to save the provider key.')
    } finally {
      setBusy(null)
    }
  }

  async function handleApply() {
    if (selectedIds.size === 0 || !liveVendor || !model) {
      setStatus(
        liveVendor
          ? 'Select an assistant, then choose a model.'
          : 'Save a provider key first, then choose a model.',
      )
      return
    }
    setBusy('apply')
    setStatus('Applying…')
    try {
      const updated = await setModelAssignments(Array.from(selectedIds), liveVendor, model)
      setSubAgents(updated)
      notifyConnectionChanged()
      setStatus('This model is now assigned to the selected assistant.')
    } catch (err) {
      setStatus(err instanceof Error ? err.message : 'Failed to apply assignment.')
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
      notifyConnectionChanged()
      setStatus('The selected assistant is back on its default model.')
    } catch {
      setStatus('Failed to clear override.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="settings-page">
      <section className="settings-foundations" aria-label="Configured data">
        <h2>Foundations</h2>
        <p className="lede">Facts collected during onboarding. Edit them here.</p>
        <FoundationsPanel />
      </section>

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
              value={keyProvider}
              onChange={(e) => handleKeyProviderChange(e.target.value)}
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
        <p className="hint">
          {liveVendor
            ? `This is the model the assistant uses on ${liveVendor}. Save a different provider key first to switch vendors.`
            : 'Save a provider key first, then pick a model.'}
        </p>
        <div className="field-grid">
          <div>
            <label htmlFor="model">Model</label>
            <select
              id="model"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={!liveVendor || busy !== null}
            >
              {(liveModels[liveVendor ?? ''] ?? []).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="panel-actions">
          <button
            type="button"
            onClick={handleApply}
            disabled={selectedIds.size === 0 || !liveVendor || !model || busy !== null}
          >
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
