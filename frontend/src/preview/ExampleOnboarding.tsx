import { useState } from 'react'
import {
  EXAMPLE_DISCOVERY,
  ONBOARDING_STEPS,
  PROVIDERS,
  summaryChecks,
  type PreviewDiscovery,
  type PreviewFoundations,
} from './exampleData'

function optionList(discovered: string[] | undefined, current: string): string[] {
  const items = [...(discovered ?? [])]
  if (current && !items.includes(current)) items.push(current)
  return items
}

export function ExampleOnboarding({
  foundations,
  onChange,
  onFinished,
}: {
  foundations: PreviewFoundations
  onChange: (next: PreviewFoundations) => void
  onFinished: () => void
}) {
  const [step, setStep] = useState(0)
  const [tokenSecret, setTokenSecret] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [discovery, setDiscovery] = useState<PreviewDiscovery | null>(
    foundations.proxmox.tokenSet ? EXAMPLE_DISCOVERY : null,
  )
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [validated, setValidated] = useState(false)

  const checks = summaryChecks(foundations)
  const last = step === ONBOARDING_STEPS.length - 1
  const nextLabel = busy ? 'Working…' : step === 6 ? 'Validate' : last ? 'Finish' : 'Continue'

  function fail(message: string) {
    setError(message)
    setBusy(false)
  }

  function handleNext() {
    setError(null)
    setBusy(true)

    if (step === 0) {
      if (!foundations.proxmox.host.trim()) return fail('Proxmox host is required')
      onChange({
        ...foundations,
        proxmox: { ...foundations.proxmox, node: foundations.proxmox.node || 'pve' },
      })
    } else if (step === 1) {
      if (!foundations.proxmox.tokenId.trim()) return fail('Proxmox Token ID is required')
    } else if (step === 2) {
      if (!tokenSecret.trim() && !foundations.proxmox.tokenSet) {
        return fail('Proxmox Token Secret is required')
      }
      const next = {
        ...foundations,
        proxmox: {
          ...foundations.proxmox,
          tokenSet: true,
          node: EXAMPLE_DISCOVERY.nodes[0],
        },
        network: {
          bridge: foundations.network.bridge || EXAMPLE_DISCOVERY.bridges[0],
          address: foundations.network.address || EXAMPLE_DISCOVERY.networks.vmbr0.address,
          gateway: foundations.network.gateway || EXAMPLE_DISCOVERY.networks.vmbr0.gateway,
        },
        storage: { pool: foundations.storage.pool || EXAMPLE_DISCOVERY.pools[0] },
      }
      setDiscovery(EXAMPLE_DISCOVERY)
      setTokenSecret('')
      onChange(next)
    } else if (step === 3) {
      if (!foundations.network.bridge.trim() || !foundations.storage.pool.trim()) {
        return fail('Bridge and storage are required')
      }
    } else if (step === 4) {
      if (!apiKey.trim() && !foundations.provider.keySet) {
        return fail('API key is required')
      }
      setApiKey('')
      onChange({ ...foundations, provider: { ...foundations.provider, keySet: true } })
    } else if (step === 5) {
      if (!foundations.tenant.name.trim() || !foundations.tenant.slug.trim()) {
        return fail('Tenant name and slug are required')
      }
    } else if (step === 6) {
      const nextProbes = { ...foundations.probes }
      for (const id of Object.keys(nextProbes)) {
        if (id !== 'ssh_key_installed') nextProbes[id] = 'pass'
      }
      onChange({ ...foundations, probes: nextProbes })
      setValidated(true)
    }

    setStep((current) => Math.min(current + 1, ONBOARDING_STEPS.length - 1))
    setBusy(false)
  }

  return (
    <section className="wizard chat-pane" aria-label="Onboarding">
      <h2>Onboarding</h2>
      <p className="lede">
        Minimum facts for a fresh Shed. You can re-run this any time to validate or change
        settings.
      </p>
      <ol className="wizard__steps preview-steps" aria-label="wizard steps">
        {ONBOARDING_STEPS.map((label, index) => (
          <li
            key={label}
            className={index === step ? 'is-current' : index < step ? 'is-done' : undefined}
          >
            <span className="preview-steps__index">{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div>
          <label htmlFor="preview-onboard-host">Proxmox IP or API URL</label>
          <input
            id="preview-onboard-host"
            value={foundations.proxmox.host}
            onChange={(e) =>
              onChange({ ...foundations, proxmox: { ...foundations.proxmox, host: e.target.value } })
            }
            placeholder="192.0.2.10"
            autoComplete="off"
          />
        </div>
      )}

      {step === 1 && (
        <div>
          <label htmlFor="preview-onboard-token-id">Proxmox Token ID</label>
          <input
            id="preview-onboard-token-id"
            value={foundations.proxmox.tokenId}
            onChange={(e) =>
              onChange({
                ...foundations,
                proxmox: { ...foundations.proxmox, tokenId: e.target.value },
              })
            }
            placeholder="USER@REALM!tokenid"
            autoComplete="off"
          />
          {foundations.proxmox.tokenSet && foundations.proxmox.tokenId ? (
            <p className="hint">Saved Token ID. Continue to confirm the secret, or paste a new ID.</p>
          ) : null}
        </div>
      )}

      {step === 2 && (
        <div>
          <p className="hint">Token ID: {foundations.proxmox.tokenId || 'not set'}</p>
          <label htmlFor="preview-onboard-token-secret">Proxmox Token Secret</label>
          <input
            id="preview-onboard-token-secret"
            type="password"
            value={tokenSecret}
            onChange={(e) => setTokenSecret(e.target.value)}
            placeholder="Token secret"
            autoComplete="off"
          />
          {foundations.proxmox.tokenSet ? (
            <p className="hint">
              Token secret is saved. Leave this blank to keep it, or paste a new secret to replace
              it.
            </p>
          ) : null}
        </div>
      )}

      {step === 3 && (
        <div>
          <p className="hint">
            Discovered from the Proxmox host. Change the bridge or storage if the default is
            wrong.
          </p>
          <label htmlFor="preview-onboard-bridge">Bridge</label>
          {optionList(discovery?.bridges, foundations.network.bridge).length ? (
            <select
              id="preview-onboard-bridge"
              value={foundations.network.bridge}
              onChange={(e) => {
                const bridge = e.target.value
                const net = discovery?.networks[bridge]
                onChange({
                  ...foundations,
                  network: {
                    ...foundations.network,
                    bridge,
                    address: net?.address || foundations.network.address,
                    gateway: net?.gateway || foundations.network.gateway,
                  },
                })
              }}
            >
              {optionList(discovery?.bridges, foundations.network.bridge).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="preview-onboard-bridge"
              value={foundations.network.bridge}
              onChange={(e) =>
                onChange({
                  ...foundations,
                  network: { ...foundations.network, bridge: e.target.value },
                })
              }
              placeholder="vmbr0"
              autoComplete="off"
            />
          )}
          <label htmlFor="preview-onboard-address">CIDR</label>
          <input
            id="preview-onboard-address"
            value={foundations.network.address}
            onChange={(e) =>
              onChange({
                ...foundations,
                network: { ...foundations.network, address: e.target.value },
              })
            }
            placeholder="192.0.2.10/24"
            autoComplete="off"
          />
          <label htmlFor="preview-onboard-gateway">Gateway</label>
          <input
            id="preview-onboard-gateway"
            value={foundations.network.gateway}
            onChange={(e) =>
              onChange({
                ...foundations,
                network: { ...foundations.network, gateway: e.target.value },
              })
            }
            placeholder="192.0.2.1"
            autoComplete="off"
          />
          <label htmlFor="preview-onboard-pool">Storage</label>
          {optionList(discovery?.pools, foundations.storage.pool).length ? (
            <select
              id="preview-onboard-pool"
              value={foundations.storage.pool}
              onChange={(e) => onChange({ ...foundations, storage: { pool: e.target.value } })}
            >
              {optionList(discovery?.pools, foundations.storage.pool).map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="preview-onboard-pool"
              value={foundations.storage.pool}
              onChange={(e) => onChange({ ...foundations, storage: { pool: e.target.value } })}
              placeholder="local-lvm"
              autoComplete="off"
            />
          )}
        </div>
      )}

      {step === 4 && (
        <div>
          <label htmlFor="preview-onboard-provider">Provider</label>
          <select
            id="preview-onboard-provider"
            value={foundations.provider.vendor}
            onChange={(e) =>
              onChange({ ...foundations, provider: { ...foundations.provider, vendor: e.target.value } })
            }
          >
            {PROVIDERS.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
          <label htmlFor="preview-onboard-api-key">API key</label>
          <input
            id="preview-onboard-api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={
              foundations.provider.keySet
                ? 'Key is saved. Paste a new one to replace it, or continue.'
                : 'A Claude subscription will not work'
            }
            autoComplete="off"
          />
        </div>
      )}

      {step === 5 && (
        <div>
          <label htmlFor="preview-onboard-name">Tenant name</label>
          <input
            id="preview-onboard-name"
            value={foundations.tenant.name}
            onChange={(e) =>
              onChange({ ...foundations, tenant: { ...foundations.tenant, name: e.target.value } })
            }
          />
          <label htmlFor="preview-onboard-slug">Tenant slug</label>
          <input
            id="preview-onboard-slug"
            value={foundations.tenant.slug}
            onChange={(e) =>
              onChange({ ...foundations, tenant: { ...foundations.tenant, slug: e.target.value } })
            }
          />
        </div>
      )}

      {step === 6 && (
        <fieldset className="group">
          <legend>Install mode</legend>
          <label>
            <input
              type="radio"
              name="preview-intent-mode"
              checked={foundations.intent.mode === 'build'}
              onChange={() =>
                onChange({ ...foundations, intent: { ...foundations.intent, mode: 'build' } })
              }
            />
            Fresh install (no adoption)
          </label>
          <label>
            <input
              type="radio"
              name="preview-intent-mode"
              checked={foundations.intent.mode === 'adopt'}
              onChange={() =>
                onChange({ ...foundations, intent: { ...foundations.intent, mode: 'adopt' } })
              }
            />
            Fresh install with adoption of services
          </label>
          {foundations.intent.mode === 'adopt' && (
            <div>
              <p className="hint">
                URLs for services that already exist. Leave blank to build that one later.
              </p>
              <label htmlFor="preview-onboard-gitlab">GitLab URL</label>
              <input
                id="preview-onboard-gitlab"
                value={foundations.intent.gitlabUrl}
                onChange={(e) =>
                  onChange({
                    ...foundations,
                    intent: { ...foundations.intent, gitlabUrl: e.target.value },
                  })
                }
              />
              <label htmlFor="preview-onboard-infisical">Infisical URL</label>
              <input
                id="preview-onboard-infisical"
                value={foundations.intent.infisicalUrl}
                onChange={(e) =>
                  onChange({
                    ...foundations,
                    intent: { ...foundations.intent, infisicalUrl: e.target.value },
                  })
                }
              />
              <label htmlFor="preview-onboard-dns">DNS URL</label>
              <input
                id="preview-onboard-dns"
                value={foundations.intent.dnsUrl}
                onChange={(e) =>
                  onChange({
                    ...foundations,
                    intent: { ...foundations.intent, dnsUrl: e.target.value },
                  })
                }
              />
              <label htmlFor="preview-onboard-k3s">k3s URL</label>
              <input
                id="preview-onboard-k3s"
                value={foundations.intent.k3sUrl}
                onChange={(e) =>
                  onChange({
                    ...foundations,
                    intent: { ...foundations.intent, k3sUrl: e.target.value },
                  })
                }
              />
            </div>
          )}
        </fieldset>
      )}

      {step === 7 && (
        <div>
          <h3>{validated && checks.every((item) => item.status === 'pass') ? 'Ready' : 'Check these results'}</h3>
          {discovery && (
            <p className="hint">
              Discovered {discovery.nodes.join(', ') || 'no nodes'}; bridges{' '}
              {discovery.bridges.join(', ') || 'none'}; pools {discovery.pools.join(', ') || 'none'}
              {foundations.network.address ? `; CIDR ${foundations.network.address}` : ''}
              {foundations.network.gateway ? `; gateway ${foundations.network.gateway}` : ''}.
            </p>
          )}
          <ul className="wizard__checks" aria-label="onboarding summary">
            {checks.map((item) => (
              <li key={item.id} data-status={item.status}>
                <strong>{item.label}</strong> — {item.status}
                {item.detail ? ` (${item.detail})` : ''}
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p role="alert">{error}</p>}

      <div className="panel-actions">
        {step > 0 && step < 7 && (
          <button
            type="button"
            className="button-secondary"
            onClick={() => {
              setError(null)
              setStep((current) => current - 1)
            }}
            disabled={busy}
          >
            Back
          </button>
        )}
        {last ? (
          <button type="button" onClick={onFinished}>
            Finish
          </button>
        ) : (
          <button type="button" onClick={handleNext} disabled={busy}>
            {nextLabel}
          </button>
        )}
      </div>
    </section>
  )
}
