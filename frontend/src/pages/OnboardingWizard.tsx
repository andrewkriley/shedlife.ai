import { useEffect, useState } from 'react'
import {
  getOnboardingStatus,
  notifyConnectionChanged,
  notifyFoundationsChanged,
  postOnboardingComplete,
  postOnboardingIntent,
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
  'Proxmox host',
  'Token ID',
  'Token Secret',
  'AI provider',
  'Tenant',
  'Install mode',
  'Summary',
] as const

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
  }
}

export function OnboardingWizard({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState(0)
  const [status, setStatus] = useState<OnboardingStatus | null>(null)
  const [host, setHost] = useState('')
  const [tokenId, setTokenId] = useState('')
  const [tokenSecret, setTokenSecret] = useState('')
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
        notifyFoundationsChanged()
      } else if (step === 3) {
        const saved = await postOnboardingProvider({ provider, api_key: apiKey })
        setStatus((prev) =>
          prev ? { ...prev, provider: saved.provider } : prev,
        )
        setApiKey('')
        notifyConnectionChanged()
      } else if (step === 4) {
        const next = await postOnboardingTenant({ name: tenantName, slug: tenantSlug })
        setStatus(next)
        notifyFoundationsChanged()
      } else if (step === 5) {
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
      setStep((current) => Math.min(current + 1, STEPS.length - 1))
    } catch (err) {
      setError(stepError(err))
    } finally {
      setBusy(false)
    }
  }

  const last = step === STEPS.length - 1
  const nextLabel = busy
    ? 'Working…'
    : step === 5
      ? 'Validate'
      : last
        ? 'Finish'
        : 'Continue'

  return (
    <section className="wizard chat-pane" aria-label="Onboarding">
      <h2>Onboarding</h2>
      <p className="lede">
        Minimum facts for a fresh Shed. You can re-run this any time to validate or
        change settings.
      </p>
      <ol className="wizard__steps" aria-label="wizard steps">
        {STEPS.map((label, index) => (
          <li key={label} className={index === step ? 'is-current' : index < step ? 'is-done' : undefined}>
            {index + 1}. {label}
          </li>
        ))}
      </ol>

      {step === 0 && (
        <div>
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
      )}

      {step === 1 && (
        <div>
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
          {status?.proxmox.api_token_set && tokenId ? (
            <p className="hint">Saved Token ID. Continue to confirm the secret, or paste a new ID.</p>
          ) : null}
        </div>
      )}

      {step === 2 && (
        <div>
          <p className="hint">
            Token ID: {tokenId || status?.proxmox.api_token_id || 'not set'}
          </p>
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
          {status?.proxmox.api_token_set ? (
            <p className="hint">
              Token secret is saved. Leave this blank to keep it, or paste a new secret to
              replace it.
            </p>
          ) : null}
        </div>
      )}

      {step === 3 && (
        <div>
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
      )}

      {step === 4 && (
        <div>
          <label htmlFor="onboard-name" title={FOUNDATION_HINTS['tenant.name']}>
            Tenant name
          </label>
          <input
            id="onboard-name"
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            title={FOUNDATION_HINTS['tenant.name']}
          />
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
      )}

      {step === 5 && (
        <fieldset className="group">
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

      {step === 6 && (
        <div>
          <h3>{summaryOk ? 'Ready' : 'Check these results'}</h3>
          {discovery && (
            <p className="hint">
              Discovered {discovery.nodes.join(', ') || 'no nodes'}; bridges{' '}
              {discovery.bridges.join(', ') || 'none'}; pools {discovery.pools.join(', ') || 'none'}.
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
        </div>
      )}

      {error && <p role="alert">{error}</p>}

      <div className="panel-actions">
        {step > 0 && step < 6 && (
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
            Back to chat
          </button>
        ) : (
          <button type="button" onClick={() => void handleNext()} disabled={busy}>
            {nextLabel}
          </button>
        )}
      </div>
    </section>
  )
}
