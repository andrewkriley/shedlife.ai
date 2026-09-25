import { useState, type FormEvent, type ReactNode } from 'react'
import { newId } from '../lib/id'
import {
  CHAT_SUGGESTIONS,
  PROVIDERS,
  READONLY_PROBES,
  foundationsYaml,
  type PreviewFoundations,
  type PreviewIssue,
} from './exampleData'

type WorkspaceView = 'chat' | 'settings' | 'onboarding'
type ReviewTab = 'foundations' | 'issues'

interface PendingApproval {
  toolName: string
  arguments: Record<string, unknown>
  subAgentId: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  turnId?: string
  verifying?: boolean
  verification?: string
  pendingApproval?: PendingApproval
}

function replyFor(prompt: string): { text: string; approval?: PendingApproval } {
  const lower = prompt.toLowerCase()
  if (lower.includes('ssh') || lower.includes('key')) {
    return {
      text: 'bootstrap.intake wants to generate a dedicated SSH key and install it on the Proxmox host. The host root password is discarded after this. Approve to continue.',
      approval: {
        toolName: 'ssh_key_installed',
        arguments: { host: '192.0.2.10', node: 'pve' },
        subAgentId: 'bootstrap.intake',
      },
    }
  }
  if (lower.includes('probe')) {
    return {
      text: 'Read-only probes are in the Foundations panel. llm_key, proxmox_api, bridge_exists, and storage_pool_exists already passed. ssh_key_installed still needs approval.',
    }
  }
  if (lower.includes('valid')) {
    return {
      text: 'Foundations look complete: tenant, Proxmox token, network, storage, and provider key are present. Field typos stay on the field — they do not become issues.',
    }
  }
  if (lower.includes('export') || lower.includes('yaml')) {
    return {
      text: 'I can export a YAML bundle with references, not secret values. Use Export YAML in Foundations when you want the file.',
    }
  }
  return {
    text: 'I can collect foundations, validate them, run predetermined pre-deploy probes, or export the YAML bundle. I will not invent a playbook.',
  }
}

export function ExampleWorkspace({
  view,
  setView,
  foundations,
  onFoundationsChange,
  issues,
  onIssuesChange,
  onboarding,
}: {
  view: WorkspaceView
  setView: (view: WorkspaceView) => void
  foundations: PreviewFoundations
  onFoundationsChange: (next: PreviewFoundations) => void
  issues: PreviewIssue[]
  onIssuesChange: (next: PreviewIssue[]) => void
  onboarding: ReactNode
}) {
  const [reviewTab, setReviewTab] = useState<ReviewTab>('foundations')

  return (
    <div className="app-shell" data-layout="single-window">
      <header className="app-header">
        <h1>The Shed</h1>
        <p
          role="status"
          aria-label="assistant connection"
          className="assistant-status assistant-status--connected"
          data-state="connected"
        >
          <span className="assistant-status__dot" aria-hidden="true" />
          AI Assistant is Connected · {foundations.provider.vendor} · preview-model
        </p>
        <div className="app-header__actions">
          {view !== 'onboarding' ? (
            <button type="button" className="button-secondary" onClick={() => setView('onboarding')}>
              Onboarding
            </button>
          ) : null}
          {view === 'settings' || view === 'onboarding' ? (
            <button type="button" className="button-secondary" onClick={() => setView('chat')}>
              Back to chat
            </button>
          ) : (
            <button type="button" className="button-secondary" onClick={() => setView('settings')}>
              Settings
            </button>
          )}
        </div>
      </header>
      <div
        className={view === 'settings' ? 'workspace workspace--hidden' : 'workspace'}
        aria-hidden={view === 'settings'}
      >
        {view === 'onboarding' ? (
          onboarding
        ) : (
          <ExampleChat
            foundations={foundations}
            onFoundationsChange={onFoundationsChange}
            onFileIssue={(issue) => onIssuesChange([issue, ...issues])}
          />
        )}
        <aside className="sidebar">
          <div className="sidebar-tabs" role="tablist" aria-label="review">
            <button
              type="button"
              role="tab"
              aria-selected={reviewTab === 'foundations'}
              className={reviewTab === 'foundations' ? 'is-active' : undefined}
              onClick={() => setReviewTab('foundations')}
            >
              Foundations
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={reviewTab === 'issues'}
              className={reviewTab === 'issues' ? 'is-active' : undefined}
              onClick={() => setReviewTab('issues')}
            >
              Issues
            </button>
          </div>
          <div className="sidebar-panel" role="tabpanel">
            {reviewTab === 'foundations' ? (
              <ExampleFoundations foundations={foundations} onChange={onFoundationsChange} />
            ) : (
              <ExampleIssues issues={issues} onChange={onIssuesChange} />
            )}
          </div>
        </aside>
      </div>
      {view === 'settings' ? (
        <ExampleSettings
          vendor={foundations.provider.vendor}
          onVendor={(vendor) =>
            onFoundationsChange({ ...foundations, provider: { ...foundations.provider, vendor } })
          }
        />
      ) : null}
      <ExampleDebugDock />
    </div>
  )
}

function ExampleChat({
  foundations,
  onFoundationsChange,
  onFileIssue,
}: {
  foundations: PreviewFoundations
  onFoundationsChange: (next: PreviewFoundations) => void
  onFileIssue: (issue: PreviewIssue) => void
}) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  function updateMessage(id: string, updater: (m: Message) => Message) {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)))
  }

  function send(text: string) {
    if (!text.trim() || sending) return
    const assistantId = newId()
    const reply = replyFor(text)
    setMessages((prev) => [
      ...prev,
      { id: newId(), role: 'user', text },
      {
        id: assistantId,
        role: 'assistant',
        text: reply.text,
        turnId: newId(),
        pendingApproval: reply.approval,
      },
    ])
    setInput('')
    setStatus(reply.approval ? 'Waiting for approval' : null)
    setSending(false)
  }

  function handleApprove(id: string, approved: boolean) {
    const message = messages.find((m) => m.id === id)
    if (!message) return
    if (approved) {
      onFoundationsChange({
        ...foundations,
        probes: { ...foundations.probes, ssh_key_installed: 'pass' },
        proxmox: { ...foundations.proxmox, node: foundations.proxmox.node || 'pve' },
      })
      updateMessage(id, (m) => ({
        ...m,
        pendingApproval: undefined,
        text: `${m.text}\n\nApproved. ssh_key_installed passed. The host root password is no longer stored.`,
      }))
      setStatus(null)
      return
    }
    onFileIssue({
      id: newId(),
      classification: 'operator',
      summary: 'operator declined ssh_key_installed',
    })
    updateMessage(id, (m) => ({
      ...m,
      pendingApproval: undefined,
      text: `${m.text}\n\nDeclined. The key was not installed. I filed that as an operator issue.`,
    }))
    setStatus(null)
  }

  function handleVerify(id: string) {
    updateMessage(id, (m) => ({
      ...m,
      verifying: false,
      verification: 'Independent verifier: the answer matches the asked playbook and does not invent steps.',
    }))
  }

  return (
    <div className="chat-pane">
      <div className="message-list" role="log" aria-label="conversation">
        {messages.length === 0 && (
          <div className="message-list__empty preview-empty">
            <p>
              Ask the bootstrap assistant to collect foundations, validate them, or run a probe.
            </p>
            <div className="preview-suggestions">
              {CHAT_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="button-secondary"
                  onClick={() => send(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} data-role={m.role} className={`message message--${m.role}`}>
            <span className="message__role">{m.role === 'user' ? 'You' : 'Shed'}</span>
            <p className="message__content">{m.text}</p>
            {m.role === 'assistant' && m.pendingApproval && (
              <div data-role="approval-request" className="message__actions preview-approval">
                <p>
                  <strong>{m.pendingApproval.subAgentId}</strong> wants to run{' '}
                  <code>{m.pendingApproval.toolName}</code> with{' '}
                  <code>{JSON.stringify(m.pendingApproval.arguments)}</code>
                </p>
                <div className="preview-approval__actions">
                  <button type="button" onClick={() => handleApprove(m.id, true)}>
                    Approve
                  </button>
                  <button
                    type="button"
                    className="button-secondary"
                    onClick={() => handleApprove(m.id, false)}
                  >
                    Decline
                  </button>
                </div>
              </div>
            )}
            {m.role === 'assistant' && m.turnId && !m.pendingApproval && (
              <div className="message__actions">
                <button type="button" className="button-secondary" onClick={() => handleVerify(m.id)}>
                  Verify
                </button>
                {m.verification && <p data-role="verification">{m.verification}</p>}
              </div>
            )}
          </div>
        ))}
      </div>
      {status && <p role="status">{status}</p>}
      <form
        className="composer"
        aria-label="composer"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <label htmlFor="preview-message" className="visually-hidden">
          Message
        </label>
        <input
          id="preview-message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask something…"
        />
        <button type="submit" disabled={!input.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}

function ExampleFoundations({
  foundations,
  onChange,
}: {
  foundations: PreviewFoundations
  onChange: (next: PreviewFoundations) => void
}) {
  const [status, setStatus] = useState<string | null>(null)

  function handleExport() {
    const yaml = foundationsYaml(foundations)
    const blob = new Blob([yaml], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'foundations.yaml'
    link.click()
    URL.revokeObjectURL(url)
    setStatus('Exported.')
  }

  return (
    <section className="panel" aria-label="foundations">
      <div className="panel-body">
        <fieldset className="group">
          <legend>Tenant</legend>
          <dl className="preview-facts">
            <div>
              <dt>Name</dt>
              <dd>{foundations.tenant.name || '—'}</dd>
            </div>
            <div>
              <dt>Slug</dt>
              <dd>{foundations.tenant.slug || '—'}</dd>
            </div>
          </dl>
        </fieldset>
        <fieldset className="group">
          <legend>Proxmox</legend>
          <dl className="preview-facts">
            <div>
              <dt>Host</dt>
              <dd>{foundations.proxmox.host || '—'}</dd>
            </div>
            <div>
              <dt>Node</dt>
              <dd>{foundations.proxmox.node || '—'}</dd>
            </div>
            <div>
              <dt>Token</dt>
              <dd>{foundations.proxmox.tokenSet ? foundations.proxmox.tokenId || 'saved' : 'not set'}</dd>
            </div>
          </dl>
        </fieldset>
        <fieldset className="group">
          <legend>Network & storage</legend>
          <dl className="preview-facts">
            <div>
              <dt>Bridge</dt>
              <dd>{foundations.network.bridge || '—'}</dd>
            </div>
            <div>
              <dt>CIDR</dt>
              <dd>{foundations.network.address || '—'}</dd>
            </div>
            <div>
              <dt>Gateway</dt>
              <dd>{foundations.network.gateway || '—'}</dd>
            </div>
            <div>
              <dt>Pool</dt>
              <dd>{foundations.storage.pool || '—'}</dd>
            </div>
          </dl>
        </fieldset>
        <fieldset className="group">
          <legend>Probes</legend>
          <ul aria-label="probes" className="probe-list">
            {[...READONLY_PROBES, 'ssh_key_installed'].map((id) => {
              const result = foundations.probes[id] ?? 'not run'
              return (
                <li key={id}>
                  <span>{id}</span>
                  <span className="preview-probe-status" data-status={result}>
                    {result}
                  </span>
                </li>
              )
            })}
          </ul>
        </fieldset>
      </div>
      <div className="panel-actions">
        <button
          type="button"
          className="button-secondary"
          onClick={() => {
            const probes = { ...foundations.probes }
            for (const id of READONLY_PROBES) probes[id] = 'pass'
            onChange({ ...foundations, probes })
            setStatus('Read-only probes passed.')
          }}
        >
          Re-run read-only probes
        </button>
        <button type="button" className="button-secondary" onClick={handleExport}>
          Export YAML
        </button>
      </div>
      {status && <p role="status">{status}</p>}
    </section>
  )
}

function ExampleIssues({
  issues,
  onChange,
}: {
  issues: PreviewIssue[]
  onChange: (next: PreviewIssue[]) => void
}) {
  const [summary, setSummary] = useState('')
  const [detail, setDetail] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onChange([
      { id: newId(), classification: 'operator', summary },
      ...issues,
    ])
    setSummary('')
    setDetail('')
    setStatus('Filed.')
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
          <label htmlFor="preview-issue-summary">Summary</label>
          <input
            id="preview-issue-summary"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            required
          />
          <label htmlFor="preview-issue-detail">Detail</label>
          <textarea
            id="preview-issue-detail"
            value={detail}
            onChange={(e) => setDetail(e.target.value)}
            required
          />
          <div className="panel-actions">
            <button type="submit">File issue</button>
          </div>
        </fieldset>
      </form>
      {status && <p role="status">{status}</p>}
    </section>
  )
}

function ExampleSettings({
  vendor,
  onVendor,
}: {
  vendor: string
  onVendor: (vendor: string) => void
}) {
  const [model, setModel] = useState('preview-model')
  const [status, setStatus] = useState<string | null>(null)

  return (
    <div className="settings-page">
      <p className="lede">
        Choose which assistant you are talking to, then pick the model it should use. A lone
        assistant is already selected.
      </p>
      <fieldset className="group">
        <legend>Connection</legend>
        <p className="hint">Preview only — changing this stays in the browser.</p>
        <label htmlFor="preview-settings-provider">Provider</label>
        <select
          id="preview-settings-provider"
          value={vendor}
          onChange={(e) => onVendor(e.target.value)}
        >
          {PROVIDERS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </fieldset>
      <fieldset className="group">
        <legend>Your assistants</legend>
        <ul aria-label="sub-agents" className="assistant-cards">
          <li className="is-selected">
            <label>
              <input type="checkbox" checked onChange={() => undefined} />
              <span>
                <strong>bootstrap.intake</strong>
                <span className="assistant-cards__meta">
                  {vendor}/{model}
                </span>
                <span className="assistant-cards__desc">
                  Collects foundations, validates them, and runs predetermined probes.
                </span>
              </span>
            </label>
          </li>
        </ul>
      </fieldset>
      <fieldset className="group">
        <legend>Change the model</legend>
        <label htmlFor="preview-settings-model">Model</label>
        <select
          id="preview-settings-model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        >
          <option value="preview-model">preview-model</option>
          <option value="preview-model-fast">preview-model-fast</option>
        </select>
        <div className="panel-actions">
          <button
            type="button"
            onClick={() => setStatus('This model is now assigned to the selected assistant.')}
          >
            Apply this model
          </button>
        </div>
      </fieldset>
      {status && <p role="status">{status}</p>}
    </div>
  )
}

function ExampleDebugDock() {
  const [open, setOpen] = useState(false)
  return (
    <section className="debug-dock" aria-label="debug">
      <div className="debug-dock__bar">
        <button type="button" className="button-secondary" onClick={() => setOpen((value) => !value)}>
          {open ? 'Hide debug' : 'Show debug'}
        </button>
        <span className="hint">Preview log — clicks stay local.</span>
      </div>
      {open ? (
        <div className="debug-console">
          <ol>
            <li>preview opened</li>
            <li>ui-only flow — no API calls</li>
          </ol>
        </div>
      ) : null}
    </section>
  )
}
