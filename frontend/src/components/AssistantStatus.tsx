import { useEffect, useState } from 'react'
import { CONNECTION_CHANGED_EVENT, getConnection, getHealth, getSubAgentSettings } from '../lib/api'

type ConnectionState = 'checking' | 'connected' | 'disconnected'

export function AssistantStatus() {
  const [state, setState] = useState<ConnectionState>('checking')
  const [detail, setDetail] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function check() {
      try {
        const health = await getHealth()
        const agents = await getSubAgentSettings()
        const connection = await getConnection().catch(() => null)
        if (!cancelled) {
          const connected = health.status === 'ok' && agents.length > 0
          setState(connected ? 'connected' : 'disconnected')
          const ref =
            health.ref && health.ref !== 'unknown' ? health.ref : null
          if (connected && connection?.configured && connection.provider && connection.model) {
            setDetail(
              ref
                ? `${connection.provider} · ${connection.model} · ${ref}`
                : `${connection.provider} · ${connection.model}`,
            )
          } else if (connected) {
            if (connection?.configured === false) {
              setDetail(ref ? `no provider key · ${ref}` : 'no provider key')
            } else {
              setDetail(ref)
            }
          } else {
            setDetail(null)
          }
        }
      } catch {
        if (!cancelled) {
          setState('disconnected')
          setDetail(null)
        }
      }
    }

    void check()
    const timer = window.setInterval(() => {
      void check()
    }, 30_000)
    window.addEventListener(CONNECTION_CHANGED_EVENT, check)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      window.removeEventListener(CONNECTION_CHANGED_EVENT, check)
    }
  }, [])

  const label =
    state === 'checking'
      ? 'Checking assistant…'
      : state === 'connected'
        ? detail
          ? `AI Assistant is Connected · ${detail}`
          : 'AI Assistant is Connected'
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
