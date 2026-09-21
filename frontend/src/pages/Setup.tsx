import { useState } from 'react'
import { completeSetup } from '../lib/api'

export function Setup({ onComplete }: { onComplete: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (password !== passwordConfirm) {
      setError('Passwords do not match.')
      return
    }
    setSubmitting(true)
    try {
      await completeSetup({ username, password })
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
      <p className="lede">Create the first operator account. The onboarding wizard collects Proxmox and the AI key next.</p>

      <label htmlFor="setup-username">Username</label>
      <input
        id="setup-username"
        type="text"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
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

      <button type="submit" disabled={submitting}>
        {submitting ? 'Working…' : 'Create operator'}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
