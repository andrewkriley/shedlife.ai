import { useState, type FormEvent } from 'react'

export function ExampleSetup({ onComplete }: { onComplete: (username: string) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!username.trim()) {
      setError('Username is required.')
      return
    }
    if (password !== passwordConfirm) {
      setError('Passwords do not match.')
      return
    }
    if (!password) {
      setError('Password is required.')
      return
    }
    onComplete(username.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="gate">
      <h1>The Shed</h1>
      <p className="lede">Create the first operator. Prerequisites come next.</p>
      <label htmlFor="preview-setup-username">Username</label>
      <input
        id="preview-setup-username"
        type="text"
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <label htmlFor="preview-setup-password">Password</label>
      <input
        id="preview-setup-password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        autoComplete="new-password"
      />
      <label htmlFor="preview-setup-password-confirm">Confirm password</label>
      <input
        id="preview-setup-password-confirm"
        type="password"
        value={passwordConfirm}
        onChange={(e) => setPasswordConfirm(e.target.value)}
        required
        autoComplete="new-password"
      />
      <button type="submit">Create operator</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}

export function ExampleLogin({
  expectedUsername,
  onLoggedIn,
}: {
  expectedUsername: string
  onLoggedIn: () => void
}) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!username.trim() || !password) {
      setError('Username and password are required.')
      return
    }
    if (expectedUsername && username.trim() !== expectedUsername) {
      setError('Login failed — check your username and password.')
      return
    }
    onLoggedIn()
  }

  return (
    <form onSubmit={handleSubmit} className="gate">
      <h1>The Shed</h1>
      <p className="lede">Welcome back. Any password works in this preview.</p>
      <label htmlFor="preview-login-username">Username</label>
      <input
        id="preview-login-username"
        name="username"
        type="text"
        autoComplete="username"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        placeholder={expectedUsername || 'admin'}
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <label htmlFor="preview-login-password">Password</label>
      <input
        id="preview-login-password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <button type="submit">Log in</button>
      {error && <p role="alert">{error}</p>}
    </form>
  )
}
