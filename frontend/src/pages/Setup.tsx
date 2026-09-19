import { useState } from 'react'
import { completeSetup } from '../lib/api'

const PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'gemini', label: 'Gemini' },
]

export function Setup({
  onComplete,
  hasOperator = false,
}: {
  onComplete: () => void
  hasOperator?: boolean
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [provider, setProvider] = useState('anthropic')
  const [apiKey, setApiKey] = useState('')
  const [galileoKey, setGalileoKey] = useState('')
  const [galileoUrl, setGalileoUrl] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!hasOperator && password !== passwordConfirm) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await completeSetup({
        email: hasOperator ? undefined : email,
        password: hasOperator ? undefined : password,
        provider,
        api_key: apiKey,
        galileo_api_key: galileoKey || undefined,
        galileo_console_url: galileoUrl || undefined,
      })
      onComplete()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="gate">
      <h1>The Shed</h1>
      <p className="lede">First-run setup. A Claude subscription will not work — use an API key.</p>

      <label htmlFor="provider">Provider</label>
      <select id="provider" value={provider} onChange={(e) => setProvider(e.target.value)}>
        {PROVIDERS.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
      </select>

      <label htmlFor="api-key">API key</label>
      <input
        id="api-key"
        type="password"
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        required
        autoComplete="off"
      />

      {!hasOperator && (
        <>
          <label htmlFor="setup-email">Email</label>
          <input
            id="setup-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label htmlFor="setup-password">Password</label>
          <input
            id="setup-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="new-password"
          />

          <label htmlFor="setup-password-confirm">Confirm password</label>
          <input
            id="setup-password-confirm"
            type="password"
            value={passwordConfirm}
            onChange={(e) => setPasswordConfirm(e.target.value)}
            required
            autoComplete="new-password"
          />
        </>
      )}

      <label htmlFor="galileo-key">Galileo API key (optional)</label>
      <input
        id="galileo-key"
        type="password"
        value={galileoKey}
        onChange={(e) => setGalileoKey(e.target.value)}
        autoComplete="off"
      />

      <label htmlFor="galileo-url">Galileo console URL (optional)</label>
      <input id="galileo-url" value={galileoUrl} onChange={(e) => setGalileoUrl(e.target.value)} />

      <button type="submit" disabled={submitting}>
        {submitting ? 'Working…' : hasOperator ? 'Save API key' : 'Create operator'}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
