import { useEffect, useState } from 'react'
import { getHealth, getSubAgentSettings } from '../lib/api'

type ConnectionState = 'checking' | 'connected' | 'disconnected'

export function AssistantStatus() {
  const [state, setState] = useState<ConnectionState>('checking')

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const health = await getHealth()
        const agents = await getSubAgentSettings()
        if (!cancelled) {
          setState(health.status === 'ok' && agents.length > 0 ? 'connected' : 'disconnected')
        }
      } catch {
        if (!cancelled) setState('disconnected')
      }
    }

    void check()
    const timer = window.setInterval(() => {
      void check()
    }, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  const label =
    state === 'checking'
      ? 'Checking assistant…'
      : state === 'connected'
        ? 'AI Assistant is Connected'
        : 'AI Assistant is disconnected'

  return (
    <p
      role="status"
      aria-label="assistant connection"
      className={`assistant-status assistant-status--${state}`}
      data-state={state}
    >
      <span className="assistant-status__dot" aria-hidden="true" />
      {label}
    </p>
  )
}
