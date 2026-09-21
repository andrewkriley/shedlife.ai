import { useEffect, useState, type InputHTMLAttributes, type SelectHTMLAttributes } from 'react'
import {
  exportFoundations,
  getFoundations,
  putFoundations,
  runProbe,
  validateFoundations,
  type FoundationsDocument,
} from '../lib/api'
import { FOUNDATION_HINTS } from '../lib/foundationsHints'

const READONLY_PROBES = [
  'llm_key',
  'outbound_https',
  'proxmox_api',
  'proxmox_capacity',
  'bridge_exists',
  'storage_pool_exists',
  'ntp_ok',
  'adopted_endpoint',
  'domain_resolves',
]

const INTENT_KEYS = ['gitlab', 'infisical', 'dns', 'k3s'] as const

function HintedLabel({
  htmlFor,
  hint,
  children,
}: {
  htmlFor: string
  hint: string
  children: string
}) {
  return (
    <label htmlFor={htmlFor} title={hint}>
      {children}
    </label>
  )
}

function HintedInput({
  hint,
  ...props
}: { hint: string } & InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} title={hint} />
}

function HintedSelect({
  hint,
  ...props
}: { hint: string } & SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} title={hint} />
}

function emptyDoc(): FoundationsDocument {
  return {
    version: 1,
    tenant: { name: '', slug: '' },
    operator: { email: '' },
    proxmox: { host: '', node: '', ssh_key_fingerprint: null, api_token_ref: '', api_token_set: false },
    network: { bridge: '', address: '', gateway: '', ntp: 'inherit' },
    storage: { pool: '' },
    domains: { intended: [] },
    intent: {
      gitlab: { mode: 'build' },
      infisical: { mode: 'build' },
      dns: { mode: 'greenfield' },
      k3s: { mode: 'build' },
    },
    probes: {},
  }
}

export function FoundationsPanel() {
  const [doc, setDoc] = useState<FoundationsDocument>(emptyDoc)
  const [tokenId, setTokenId] = useState('')
  const [tokenSecret, setTokenSecret] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [status, setStatus] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  async function refresh() {
    const next = await getFoundations()
    setDoc({ ...emptyDoc(), ...next, probes: next.probes ?? {} })
  }

  useEffect(() => {
    refresh().catch(() => setStatus('Failed to load foundations.'))
  }, [])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setBusy('save')
    setStatus('Saving…')
    try {
      const payload: FoundationsDocument = {
        ...doc,
        proxmox: { ...doc.proxmox },
      }
      delete payload.proxmox.api_token_set
      if (tokenId.trim() || tokenSecret.trim()) {
        if (!tokenId.trim() || !tokenSecret.trim()) {
          setErrors({
            'proxmox.api_token_id': 'required with the token secret',
            'proxmox.api_token_secret': 'required with the token id',
          })
          setStatus('Token ID and Token Secret must be saved together.')
          return
        }
        payload.proxmox.api_token_id = tokenId.trim()
        payload.proxmox.api_token_secret = tokenSecret.trim()
      }
      const saved = await putFoundations(payload)
      setDoc({ ...emptyDoc(), ...saved, probes: saved.probes ?? {} })
      setTokenId('')
      setTokenSecret('')
      setErrors({})
      setStatus('Saved.')
    } catch {
      setStatus('Failed to save foundations.')
    } finally {
      setBusy(null)
    }
  }

  async function handleValidate() {
    setBusy('validate')
    setStatus('Validating…')
    try {
      const result = await validateFoundations()
      setErrors(result.errors)
      setStatus(result.ok ? 'Valid.' : 'Field errors — not issues.')
    } catch {
      setStatus('Failed to validate.')
    } finally {
      setBusy(null)
    }
  }

  async function handleExport() {
    setBusy('export')
    setStatus('Exporting…')
    try {
      const yaml = await exportFoundations()
      const blob = new Blob([yaml], { type: 'text/yaml' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'foundations.yaml'
      link.click()
      URL.revokeObjectURL(url)
      setStatus('Exported.')
    } catch {
      setStatus('Failed to export.')
    } finally {
      setBusy(null)
    }
  }

  async function handleProbe(id: string) {
    setBusy(`probe:${id}`)
    setStatus(`Running ${id}…`)
    try {
      const result = await runProbe(id)
      await refresh()
      setStatus(`${id}: ${result.status}`)
    } catch {
      setStatus(`Failed to run ${id}.`)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="panel" aria-label="foundations">
      <form className="panel-form" onSubmit={handleSave}>
        <div className="panel-body">
          <fieldset className="group">
            <legend>Tenant</legend>
            <div className="field-grid">
              <div>
                <HintedLabel htmlFor="tenant-name" hint={FOUNDATION_HINTS['tenant.name']}>
                  Tenant name
                </HintedLabel>
                <HintedInput
                  id="tenant-name"
                  hint={FOUNDATION_HINTS['tenant.name']}
                  value={doc.tenant.name}
                  onChange={(e) => setDoc({ ...doc, tenant: { ...doc.tenant, name: e.target.value } })}
                />
                {errors['tenant.name'] && <p className="field-error">{errors['tenant.name']}</p>}
              </div>
              <div>
                <HintedLabel htmlFor="tenant-slug" hint={FOUNDATION_HINTS['tenant.slug']}>
                  Tenant slug
                </HintedLabel>
                <HintedInput
                  id="tenant-slug"
                  hint={FOUNDATION_HINTS['tenant.slug']}
                  value={doc.tenant.slug}
                  onChange={(e) => setDoc({ ...doc, tenant: { ...doc.tenant, slug: e.target.value } })}
                />
                {errors['tenant.slug'] && <p className="field-error">{errors['tenant.slug']}</p>}
              </div>
            </div>
            <HintedLabel htmlFor="operator-email" hint={FOUNDATION_HINTS['operator.email']}>
              Operator email
            </HintedLabel>
            <HintedInput
              id="operator-email"
              hint={FOUNDATION_HINTS['operator.email']}
              type="email"
              value={doc.operator.email}
              onChange={(e) => setDoc({ ...doc, operator: { email: e.target.value } })}
            />
            {errors['operator.email'] && <p className="field-error">{errors['operator.email']}</p>}
          </fieldset>

          <fieldset className="group">
            <legend>Proxmox</legend>
            <div className="field-grid">
              <div>
                <HintedLabel htmlFor="proxmox-host" hint={FOUNDATION_HINTS['proxmox.host']}>
                  Proxmox host
                </HintedLabel>
                <HintedInput
                  id="proxmox-host"
                  hint={FOUNDATION_HINTS['proxmox.host']}
                  value={doc.proxmox.host}
                  onChange={(e) => setDoc({ ...doc, proxmox: { ...doc.proxmox, host: e.target.value } })}
                />
              </div>
              <div>
                <HintedLabel htmlFor="proxmox-node" hint={FOUNDATION_HINTS['proxmox.node']}>
                  Proxmox node
                </HintedLabel>
                <HintedInput
                  id="proxmox-node"
                  hint={FOUNDATION_HINTS['proxmox.node']}
                  value={doc.proxmox.node}
                  onChange={(e) => setDoc({ ...doc, proxmox: { ...doc.proxmox, node: e.target.value } })}
                />
              </div>
            </div>
            <div className="field-grid">
              <div>
                <HintedLabel htmlFor="proxmox-token-id" hint={FOUNDATION_HINTS['proxmox.api_token_id']}>
                  Proxmox Token ID
                </HintedLabel>
                <HintedInput
                  id="proxmox-token-id"
                  hint={FOUNDATION_HINTS['proxmox.api_token_id']}
                  value={tokenId}
                  onChange={(e) => setTokenId(e.target.value)}
                  placeholder={
                    doc.proxmox.api_token_set
                      ? 'Token is saved. Paste a new ID to replace it.'
                      : 'USER@REALM!tokenid'
                  }
                  autoComplete="off"
                />
                {errors['proxmox.api_token_id'] && (
                  <p className="field-error">{errors['proxmox.api_token_id']}</p>
                )}
              </div>
              <div>
                <HintedLabel
                  htmlFor="proxmox-token-secret"
                  hint={FOUNDATION_HINTS['proxmox.api_token_secret']}
                >
                  Proxmox Token Secret
                </HintedLabel>
                <HintedInput
                  id="proxmox-token-secret"
                  hint={FOUNDATION_HINTS['proxmox.api_token_secret']}
                  type="password"
                  value={tokenSecret}
                  onChange={(e) => setTokenSecret(e.target.value)}
                  placeholder={
                    doc.proxmox.api_token_set
                      ? 'Secret is saved. Paste a new one to replace it.'
                      : 'token secret'
                  }
                  autoComplete="off"
                />
                {errors['proxmox.api_token_secret'] && (
                  <p className="field-error">{errors['proxmox.api_token_secret']}</p>
                )}
              </div>
            </div>
            {doc.proxmox.api_token_set && !tokenId && !tokenSecret && (
              <p className="hint">A token is saved. Leave both blank to keep it.</p>
            )}
            {errors['proxmox.api_token'] && <p className="field-error">{errors['proxmox.api_token']}</p>}
            {doc.proxmox.ssh_key_fingerprint && (
              <>
                <HintedLabel
                  htmlFor="proxmox-ssh-fingerprint"
                  hint={FOUNDATION_HINTS['proxmox.ssh_key_fingerprint']}
                >
                  SSH key fingerprint
                </HintedLabel>
                <HintedInput
                  id="proxmox-ssh-fingerprint"
                  hint={FOUNDATION_HINTS['proxmox.ssh_key_fingerprint']}
                  value={doc.proxmox.ssh_key_fingerprint}
                  readOnly
                />
              </>
            )}
          </fieldset>

          <fieldset className="group">
            <legend>Network</legend>
            <div className="field-grid">
              <div>
                <HintedLabel htmlFor="network-bridge" hint={FOUNDATION_HINTS['network.bridge']}>
                  Bridge
                </HintedLabel>
                <HintedInput
                  id="network-bridge"
                  hint={FOUNDATION_HINTS['network.bridge']}
                  value={doc.network.bridge}
                  onChange={(e) => setDoc({ ...doc, network: { ...doc.network, bridge: e.target.value } })}
                />
              </div>
              <div>
                <HintedLabel htmlFor="network-address" hint={FOUNDATION_HINTS['network.address']}>
                  Address (CIDR)
                </HintedLabel>
                <HintedInput
                  id="network-address"
                  hint={FOUNDATION_HINTS['network.address']}
                  value={doc.network.address}
                  onChange={(e) =>
                    setDoc({ ...doc, network: { ...doc.network, address: e.target.value } })
                  }
                />
                {errors['network.address'] && <p className="field-error">{errors['network.address']}</p>}
              </div>
              <div>
                <HintedLabel htmlFor="network-gateway" hint={FOUNDATION_HINTS['network.gateway']}>
                  Gateway
                </HintedLabel>
                <HintedInput
                  id="network-gateway"
                  hint={FOUNDATION_HINTS['network.gateway']}
                  value={doc.network.gateway}
                  onChange={(e) =>
                    setDoc({ ...doc, network: { ...doc.network, gateway: e.target.value } })
                  }
                />
              </div>
              <div>
                <HintedLabel htmlFor="network-ntp" hint={FOUNDATION_HINTS['network.ntp']}>
                  NTP
                </HintedLabel>
                <HintedInput
                  id="network-ntp"
                  hint={FOUNDATION_HINTS['network.ntp']}
                  value={doc.network.ntp}
                  onChange={(e) => setDoc({ ...doc, network: { ...doc.network, ntp: e.target.value } })}
                />
              </div>
            </div>
          </fieldset>

          <fieldset className="group">
            <legend>Storage</legend>
            <HintedLabel htmlFor="storage-pool" hint={FOUNDATION_HINTS['storage.pool']}>
              Storage pool
            </HintedLabel>
            <HintedInput
              id="storage-pool"
              hint={FOUNDATION_HINTS['storage.pool']}
              value={doc.storage.pool}
              onChange={(e) => setDoc({ ...doc, storage: { pool: e.target.value } })}
            />
          </fieldset>

          <fieldset className="group">
            <legend>Domains</legend>
            <HintedLabel htmlFor="domains" hint={FOUNDATION_HINTS['domains.intended']}>
              Intended domains
            </HintedLabel>
            <HintedInput
              id="domains"
              hint={FOUNDATION_HINTS['domains.intended']}
              value={doc.domains.intended.join(', ')}
              onChange={(e) =>
                setDoc({
                  ...doc,
                  domains: {
                    intended: e.target.value
                      .split(',')
                      .map((part) => part.trim())
                      .filter(Boolean),
                  },
                })
              }
            />
          </fieldset>

          <fieldset className="group">
            <legend>Platform intent</legend>
            <div className="intent-grid">
              {INTENT_KEYS.map((key) => (
                <fieldset key={key}>
                  <legend>{key}</legend>
                  <HintedLabel
                    htmlFor={`intent-${key}-mode`}
                    hint={key === 'dns' ? FOUNDATION_HINTS['intent.mode.dns'] : FOUNDATION_HINTS['intent.mode.build']}
                  >
                    Mode
                  </HintedLabel>
                  <HintedSelect
                    id={`intent-${key}-mode`}
                    hint={key === 'dns' ? FOUNDATION_HINTS['intent.mode.dns'] : FOUNDATION_HINTS['intent.mode.adopt']}
                    value={doc.intent[key]?.mode ?? (key === 'dns' ? 'greenfield' : 'build')}
                    onChange={(e) =>
                      setDoc({
                        ...doc,
                        intent: { ...doc.intent, [key]: { ...doc.intent[key], mode: e.target.value } },
                      })
                    }
                  >
                    {key === 'dns' ? (
                      <>
                        <option value="greenfield">greenfield</option>
                        <option value="brownfield">brownfield</option>
                      </>
                    ) : (
                      <>
                        <option value="build">build</option>
                        <option value="adopt">adopt</option>
                      </>
                    )}
                  </HintedSelect>
                  {(doc.intent[key]?.mode === 'adopt' || doc.intent[key]?.mode === 'brownfield') && (
                    <>
                      <HintedLabel htmlFor={`intent-${key}-url`} hint={FOUNDATION_HINTS['intent.url']}>
                        URL
                      </HintedLabel>
                      <HintedInput
                        id={`intent-${key}-url`}
                        hint={FOUNDATION_HINTS['intent.url']}
                        value={doc.intent[key]?.url ?? ''}
                        onChange={(e) =>
                          setDoc({
                            ...doc,
                            intent: { ...doc.intent, [key]: { ...doc.intent[key], url: e.target.value } },
                          })
                        }
                      />
                    </>
                  )}
                </fieldset>
              ))}
            </div>
          </fieldset>

          <fieldset className="group">
            <legend>Probes</legend>
            <ul aria-label="probes" className="probe-list">
              {READONLY_PROBES.map((id) => {
                const result = doc.probes[id]
                return (
                  <li key={id}>
                    <span>
                      {id}: {result?.status ?? 'not run'}
                    </span>
                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => handleProbe(id)}
                      disabled={busy !== null}
                    >
                      {busy === `probe:${id}` ? 'Running…' : `Re-run ${id}`}
                    </button>
                  </li>
                )
              })}
              <li>ssh_key_installed: {doc.probes.ssh_key_installed?.status ?? 'not run'} (via chat approval)</li>
            </ul>
          </fieldset>
        </div>

        <div className="panel-actions">
          <button type="submit" disabled={busy !== null}>
            {busy === 'save' ? 'Saving…' : 'Save schema'}
          </button>
          <button type="button" className="button-secondary" onClick={handleValidate} disabled={busy !== null}>
            {busy === 'validate' ? 'Validating…' : 'Validate'}
          </button>
          <button type="button" className="button-secondary" onClick={handleExport} disabled={busy !== null}>
            {busy === 'export' ? 'Exporting…' : 'Export YAML'}
          </button>
        </div>
      </form>
      {status && <p role="status">{status}</p>}
    </section>
  )
}
