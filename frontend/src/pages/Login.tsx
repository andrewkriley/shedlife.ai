import { useState } from 'react'
import { login } from '../lib/api'

export function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      await login(username, password)
      onLoggedIn()
    } catch {
      setError('Login failed — check your username and password.')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="gate">
      <h1>The Shed</h1>
      <p className="lede">Welcome back.</p>
      <label htmlFor="username">Username</label>
      <input
        id="username"
        name="username"
        type="text"
        inputMode="text"
        autoComplete="username"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        placeholder="admin"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <label htmlFor="password">Password</label>
      <input
        id="password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <button type="submit">Log in</button>
      {error && <p role="alert">{error}</p>}
      {import.meta.env.DEV ? (
        <p className="hint">
          <a href="#/preview">Preview the UI-only example flow</a>
        </p>
      ) : null}
    </form>
  )
}
