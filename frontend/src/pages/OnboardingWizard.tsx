import { useEffect, useState } from 'react'
import {
  getOnboardingStatus,
  notifyConnectionChanged,
  notifyFoundationsChanged,
  postOnboardingComplete,
  postOnboardingIntent,
  postOnboardingNetwork,
  postOnboardingProvider,
  postOnboardingProxmox,
  postOnboardingTenant,
  type OnboardingCheck,
  type OnboardingStatus,
} from '../lib/api'
import { FOUNDATION_HINTS } from '../lib/foundationsHints'

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
]

const STEPS = [
  { title: 'Proxmox IP', lede: 'The first host. An address or API URL is enough.' },
  { title: 'Proxmox Token ID', lede: 'USER@REALM!tokenid. The secret is the next step.' },
  { title: 'Proxmox Token Secret', lede: 'Stored locally. It is not shown again after you continue.' },
  { title: 'Network & storage', lede: 'Discovered from the Proxmox host. Change a default if it is wrong.' },
  { title: 'AI provider', lede: 'The key chat will use. A Claude subscription will not work.' },
  { title: 'Tenant', lede: 'A name and slug for this Shed.' },
  { title: 'Install mode', lede: 'Build fresh, or adopt services that already exist.' },
  { title: 'Ready', lede: '' },
] as const

function optionList(discovered: string[] | undefined, current: string): string[] {
  const items = [...(discovered ?? [])]
  if (current && !items.includes(current)) items.push(current)
  return items
}

function stepError(err: unknown): string {
  return err instanceof Error ? err.message : 'Onboarding step failed'
}

function mergeStatus(
  prev: OnboardingStatus | null,
  next: OnboardingStatus,
): OnboardingStatus {
  return {
    ...prev,
    ...next,
    proxmox: {
      ...prev?.proxmox,
      ...next.proxmox,
      api_token_id: next.proxmox.api_token_id || prev?.proxmox.api_token_id || '',
      api_token_set: Boolean(next.proxmox.api_token_set || prev?.proxmox.api_token_set),
    },
    provider: {
      ...prev?.provider,
      ...next.provider,
      api_key_set: Boolean(next.provider?.api_key_set || prev?.provider.api_key_set),
    },
    network: {
      ...prev?.network,
      ...next.network,
    },
    storage: {
      ...prev?.storage,
      ...next.storage,
    },
    discovery: next.discovery ?? prev?.discovery ?? null,
  }
}

function summaryLede(host: string, tenantName: string): string {
  const prox = host.trim() || 'the first host'
  if (tenantName.trim()) {
    return `Proxmox is ${prox}. Tenant is ${tenantName.trim()}. Tokens and the provider key are saved locally.`
  }
  return `Proxmox is ${prox}. Tokens and the provider key are saved locally.`
}

export function OnboardingWizard({
  onFinished,
  onContinueToDeploy,
}: {
  onFinished: () => void
  onContinueToDeploy?: () => void
}) {
  const [step, setStep] = useState(0)
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [host, setHost] = useState('')
  const [tokenId, setTokenId] = useState('')
  const [tokenSecret, setTokenSecret] = useState('')
  const [bridge, setBridge] = useState('')
  const [address, setAddress] = useState('')
  const [gateway, setGateway] = useState('')
  const [pool, setPool] = useState('')
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [tenantSlug, setTenantSlug] = useState('')
  const [intentMode, setIntentMode] = useState<'build' | 'adopt'>('build')
  const [gitlabUrl, setGitlabUrl] = useState('')
  const [infisicalUrl, setInfisicalUrl] = useState('')
  const [dnsUrl, setDnsUrl] = useState('')
  const [k3sUrl, setK3sUrl] = useState('')
  const [discovery, setDiscovery] = useState<OnboardingStatus['discovery']>(null)
  const [checks, setChecks] = useState<OnboardingCheck[] | null>(null)
  const [summaryOk, setSummaryOk] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    getOnboardingStatus()
      .then((current) => {
        setStatus(current)
        setHost(current.proxmox.host)
        setTokenId(current.proxmox.api_token_id || '')
        setBridge(current.network.bridge)
        setAddress(current.network.address || '')
        setGateway(current.network.gateway || '')
        setPool(current.storage.pool)
        setTenantName(current.tenant.name)
        setTenantSlug(current.tenant.slug)
        if (current.provider.vendor) setProvider(current.provider.vendor)
        setIntentMode(current.intent.mode)
        setGitlabUrl(current.intent.services.gitlab?.url || '')
        setInfisicalUrl(current.intent.services.infisical?.url || '')
        setDnsUrl(current.intent.services.dns?.url || '')
        setK3sUrl(current.intent.services.k3s?.url || '')
      })
      .catch(() => setError('Could not load current settings.'))
  }, [])

  async function handleNext() {
    setError(null)
    setBusy(true)
    try {
      if (step === 0) {
        const next = await postOnboardingProxmox({ host })
        setStatus((prev) => mergeStatus(prev, next))
        notifyFoundationsChanged()
      } else if (step === 2) {
        if (!tokenSecret.trim() && !status?.proxmox.api_token_set) {
          throw new Error('Proxmox Token Secret is required')
        }
        const replacing = Boolean(tokenSecret.trim())
        const next = await postOnboardingProxmox(
          replacing
            ? {
                api_token_id: tokenId,
                api_token_secret: tokenSecret,
                discover: true,
              }
            : { discover: true },
        )
        setStatus((prev) => mergeStatus(prev, next))
        setDiscovery(next.discovery ?? null)
        setTokenId(next.proxmox.api_token_id || tokenId)
        setTokenSecret('')
        setBridge(next.network.bridge || next.discovery?.bridges?.[0] || bridge)
        setAddress(next.network.address || next.discovery?.address || address)
        setGateway(next.network.gateway || next.discovery?.gateway || gateway)
        setPool(next.storage.pool || next.discovery?.pools?.[0] || pool)
        notifyFoundationsChanged()
      } else if (step === 3) {
        const next = await postOnboardingNetwork({ bridge, address, gateway, pool })
        setStatus((prev) => mergeStatus(prev, next))
        notifyFoundationsChanged()
      } else if (step === 4) {
        const saved = await postOnboardingProvider({ provider, api_key: apiKey })
        setStatus((prev) =>
          prev ? { ...prev, provider: saved.provider } : prev,
        )
        setApiKey('')
        notifyConnectionChanged()
      } else if (step === 5) {
        const next = await postOnboardingTenant({ name: tenantName, slug: tenantSlug })
        setStatus(next)
        notifyFoundationsChanged()
      } else if (step === 6) {
        const next = await postOnboardingIntent({
          mode: intentMode,
          gitlab_url: gitlabUrl,
          infisical_url: infisicalUrl,
          dns_url: dnsUrl,
          k3s_url: k3sUrl,
        })
        setStatus(next)
        notifyFoundationsChanged()
        const summary = await postOnboardingComplete()
        setChecks(summary.checks)
        setSummaryOk(summary.ok)
        setStatus(summary.status)
        notifyFoundationsChanged()
      }
      setStep((current) => (checks !== null && current < 6 ? 7 : Math.min(current + 1, STEPS.length - 1)))
    } catch (err) {
      setError(stepError(err))
    } finally {
      setBusy(false)
    }
  }

  const last = step === STEPS.length - 1
  const current = STEPS[step]
  const nextLabel = busy
    ? 'Working…'
    : step === 6
      ? 'Validate'
      : last
        ? 'Finish'
        : 'Continue'

  const reviewRows = [
    { step: 0, title: 'Proxmox IP', value: host || status?.proxmox.host || 'Not set' },
    { step: 1, title: 'Proxmox Token ID', value: tokenId || status?.proxmox.api_token_id || 'Not set' },
    { step: 2, title: 'Proxmox Token Secret', value: status?.proxmox.api_token_set ? 'Saved' : 'Not set' },
    {
      step: 3,
      title: 'Network & storage',
      value: [bridge || status?.network.bridge, address || status?.network.address, pool || status?.storage.pool]
        .filter(Boolean)
        .join(' · ') || 'Not set',
    },
    {
      step: 4,
      title: 'AI provider',
      value: status?.provider.api_key_set ? status.provider.vendor || provider : 'Not set',
    },
    {
      step: 5,
      title: 'Tenant',
      value: tenantName && tenantSlug ? `${tenantName} (${tenantSlug})` : 'Not set',
    },
    { step: 6, title: 'Install mode', value: intentMode === 'adopt' ? 'Adopt' : 'Build' },
  ]

  return (
    <section className="journey chat-pane" aria-label="Onboarding">
      <p className="journey-kicker">Onboarding</p>
      {last ? null : (
        <>
          <ol className="step-dots" aria-label="wizard steps">
            {STEPS.map((entry, index) => (
              <li
                key={entry.title}
                className={index === step ? 'is-current' : index < step ? 'is-done' : undefined}
              >
                <span className="visually-hidden">
                  {entry.title}
                  {index === step ? ' (current)' : index < step ? ' (done)' : ''}
                </span>
              </li>
            ))}
          </ol>
          <p className="journey-count">{`${step + 1} of ${STEPS.length}`}</p>
          <h1 className="journey__title">{current.title}</h1>
          <p className="journey__lede">{current.lede}</p>
        </>
      )}

      {step === 0 && (
        <div className="journey-form">
          <div className="journey-field">
            <label htmlFor="onboard-host" title={FOUNDATION_HINTS['proxmox.host']}>
              Proxmox IP or API URL
            </label>
            <input
              id="onboard-host"
              value={host}
              onChange={(e) => setHost(e.target.value)}
              title={FOUNDATION_HINTS['proxmox.host']}
              placeholder="192.0.2.10"
              autoComplete="off"
            />
          </div>
        </div>
      )}

      {step === 1 && (
        <div className="journey-form">
          <div className="journey-field">
            <label htmlFor="onboard-token-id" title={FOUNDATION_HINTS['proxmox.api_token_id']}>
              Proxmox Token ID
            </label>
            <input
              id="onboard-token-id"
              value={tokenId}
              onChange={(e) => setTokenId(e.target.value)}
              title={FOUNDATION_HINTS['proxmox.api_token_id']}
              placeholder="USER@REALM!tokenid"
              autoComplete="off"
            />
          </div>
          {status?.proxmox.api_token_set && tokenId ? (
            <p className="hint">Saved Token ID. Continue to confirm the secret, or paste a new ID.</p>
          ) : null}
        </div>
      )}

      {step === 2 && (
        <div className="journey-form">
          <p className="hint">Token ID: {tokenId || status?.proxmox.api_token_id || 'not set'}</p>
          <div className="journey-field">
            <label htmlFor="onboard-token-secret" title={FOUNDATION_HINTS['proxmox.api_token_secret']}>
              Proxmox Token Secret
            </label>
            <input
              id="onboard-token-secret"
              type="password"
              value={tokenSecret}
              onChange={(e) => setTokenSecret(e.target.value)}
              title={FOUNDATION_HINTS['proxmox.api_token_secret']}
              placeholder="Token secret"
              autoComplete="off"
            />
          </div>
          {status?.proxmox.api_token_set ? (
            <p className="hint">
              Token secret is saved. Leave this blank to keep it, or paste a new secret to
              replace it.
            </p>
          ) : null}
        </div>
      )}

      {step === 3 && (
        <div className="journey-form">
          <div className="journey-field">
            <label htmlFor="onboard-bridge" title={FOUNDATION_HINTS['network.bridge']}>
              Bridge
            </label>
            {optionList(discovery?.bridges, bridge).length ? (
              <select
                id="onboard-bridge"
                value={bridge}
                title={FOUNDATION_HINTS['network.bridge']}
                onChange={(e) => {
                  const nextBridge = e.target.value
                  setBridge(nextBridge)
                  const net = discovery?.networks?.[nextBridge]
                  if (net?.address) setAddress(net.address)
                  if (net?.gateway) setGateway(net.gateway)
                }}
              >
                {optionList(discovery?.bridges, bridge).map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="onboard-bridge"
                value={bridge}
                onChange={(e) => setBridge(e.target.value)}
                title={FOUNDATION_HINTS['network.bridge']}
                placeholder="vmbr0"
                autoComplete="off"
              />
            )}
          </div>
          <div className="journey-field">
            <label htmlFor="onboard-address" title={FOUNDATION_HINTS['network.address']}>
              CIDR
            </label>
            <input
              id="onboard-address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              title={FOUNDATION_HINTS['network.address']}
              placeholder="192.0.2.10/24"
              autoComplete="off"
            />
          </div>
          <div className="journey-field">
            <label htmlFor="onboard-gateway" title={FOUNDATION_HINTS['network.gateway']}>
              Gateway
            </label>
            <input
              id="onboard-gateway"
              value={gateway}
              onChange={(e) => setGateway(e.target.value)}
              title={FOUNDATION_HINTS['network.gateway']}
              placeholder="192.0.2.1"
              autoComplete="off"
            />
          </div>
          <div className="journey-field">
            <label htmlFor="onboard-pool" title={FOUNDATION_HINTS['storage.pool']}>
              Storage
            </label>
            {optionList(discovery?.pools, pool).length ? (
              <select
                id="onboard-pool"
                value={pool}
                title={FOUNDATION_HINTS['storage.pool']}
                onChange={(e) => setPool(e.target.value)}
              >
                {optionList(discovery?.pools, pool).map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="onboard-pool"
                value={pool}
                onChange={(e) => setPool(e.target.value)}
                title={FOUNDATION_HINTS['storage.pool']}
                placeholder="local-lvm"
                autoComplete="off"
              />
            )}
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="journey-form">
          <div className="journey-field">
            <label htmlFor="onboard-provider">Provider</label>
            <select
              id="onboard-provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              {PROVIDERS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="journey-field">
            <label htmlFor="onboard-api-key">API key</label>
            <input
              id="onboard-api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={
                status?.provider.api_key_set
                  ? 'Key is saved. Paste a new one to replace it, or continue.'
                  : 'A Claude subscription will not work'
              }
              autoComplete="off"
            />
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="journey-form">
          <div className="journey-field">
            <label htmlFor="onboard-name" title={FOUNDATION_HINTS['tenant.name']}>
              Tenant name
            </label>
            <input
              id="onboard-name"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              title={FOUNDATION_HINTS['tenant.name']}
            />
          </div>
          <div className="journey-field">
            <label htmlFor="onboard-slug" title={FOUNDATION_HINTS['tenant.slug']}>
              Tenant slug
            </label>
            <input
              id="onboard-slug"
              value={tenantSlug}
              onChange={(e) => setTenantSlug(e.target.value)}
              title={FOUNDATION_HINTS['tenant.slug']}
            />
          </div>
        </div>
      )}

      {step === 6 && (
        <fieldset className="group journey-form">
          <legend>Install mode</legend>
          <label>
            <input
              type="radio"
              name="intent-mode"
              checked={intentMode === 'build'}
              onChange={() => setIntentMode('build')}
            />
            Fresh install (no adoption)
          </label>
          <label>
            <input
              type="radio"
              name="intent-mode"
              checked={intentMode === 'adopt'}
              onChange={() => setIntentMode('adopt')}
            />
            Fresh install with adoption of services
          </label>
          {intentMode === 'adopt' && (
            <div>
              <p className="hint">URLs for services that already exist. Leave blank to build that one later.</p>
              <label htmlFor="onboard-gitlab">GitLab URL</label>
              <input id="onboard-gitlab" value={gitlabUrl} onChange={(e) => setGitlabUrl(e.target.value)} />
              <label htmlFor="onboard-infisical">Infisical URL</label>
              <input
                id="onboard-infisical"
                value={infisicalUrl}
                onChange={(e) => setInfisicalUrl(e.target.value)}
              />
              <label htmlFor="onboard-dns">DNS URL</label>
              <input id="onboard-dns" value={dnsUrl} onChange={(e) => setDnsUrl(e.target.value)} />
              <label htmlFor="onboard-k3s">k3s URL</label>
              <input id="onboard-k3s" value={k3sUrl} onChange={(e) => setK3sUrl(e.target.value)} />
            </div>
          )}
        </fieldset>
      )}

      {step === 7 && (
        <>
          <h1 className="journey__title">{summaryOk ? 'Ready' : 'Check these results'}</h1>
          <p className="journey__lede">{summaryLede(host || status?.proxmox.host || '', tenantName)}</p>
          <div className="journey-list" aria-label="Onboarding review">
            {reviewRows.map((row) => (
              <button
                key={row.title}
                type="button"
                className="review-row"
                onClick={() => {
                  setError(null)
                  setStep(row.step)
                }}
              >
                <span className="review-row__title">{row.title}</span>
                <span className="review-row__value">{row.value}</span>
              </button>
            ))}
          </div>
          {discovery && (
            <p className="hint">
              Discovered {discovery.nodes.join(', ') || 'no nodes'}; bridges{' '}
              {discovery.bridges.join(', ') || 'none'}; pools {discovery.pools.join(', ') || 'none'}
              {discovery.address ? `; CIDR ${discovery.address}` : ''}
              {discovery.gateway ? `; gateway ${discovery.gateway}` : ''}.
            </p>
          )}
          <ul className="wizard__checks" aria-label="onboarding summary">
            {(checks ?? []).map((item) => (
              <li key={item.id} data-status={item.status}>
                <strong>{item.label}</strong> — {item.status}
                {item.detail ? ` (${item.detail})` : ''}
              </li>
            ))}
          </ul>
          <section className="journey-next" aria-label="Next phase">
            <p className="journey-next__title">Deploy is next</p>
            <p className="journey__lede">
              GitLab, Infisical, DNS, K3S, the AWS landing zone, Proxmox templates, and StepCA —
              not MVP yet.
            </p>
          </section>
        </>
      )}

      {error && <p role="alert">{error}</p>}

      <div className="journey-actions">
        {last ? (
          <>
            <button type="button" onClick={() => (onContinueToDeploy ?? onFinished)()}>
              Continue to Deploy
            </button>
            <button type="button" className="button-secondary" onClick={onFinished}>
              Back to chat
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => void handleNext()} disabled={busy}>
              {nextLabel}
            </button>
            {step > 0 ? (
              <button
                type="button"
                className="button-secondary"
                onClick={() => {
                  setError(null)
                  setStep((currentStep) => currentStep - 1)
                }}
                disabled={busy}
              >
                Back
              </button>
            ) : null}
          </>
        )}
      </div>
    </section>
  )
}
