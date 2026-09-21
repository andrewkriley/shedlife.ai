import { useEffect, useState } from 'react'
import {
  getDebugLogs,
  getDebugStatus,
  postDebugEvent,
  setDebugEnabled,
  type DebugEvent,
} from '../lib/api'
import { formatDebugLine } from '../lib/debugTime'

export function DebugDock() {
  const [enabled, setEnabled] = useState(false)
  const [events, setEvents] = useState<DebugEvent[]>([])

  async function refresh() {
    try {
      const status = await getDebugStatus()
      setEnabled(status.enabled)
      if (status.enabled) {
        const logs = await getDebugLogs()
        setEvents(logs.events)
      } else {
        setEvents([])
      }
    } catch {
      setEnabled(false)
      setEvents([])
    }
  }

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, 2000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!enabled) return

    function onClick(event: MouseEvent) {
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest('button')
      if (!button || button.closest('.debug-dock')) return
      const name = button.textContent?.trim() || button.getAttribute('aria-label') || 'button'
      void postDebugEvent({ event: 'click', message: `Clicked ${name}`, detail: { name } })
    }

    function onError(event: ErrorEvent) {
      void postDebugEvent({
        event: 'error',
        level: 'error',
        message: event.message,
      })
    }

    document.addEventListener('click', onClick)
    window.addEventListener('error', onError)
    return () => {
      document.removeEventListener('click', onClick)
      window.removeEventListener('error', onError)
    }
  }, [enabled])

  async function toggle() {
    const next = !enabled
    try {
      const status = await setDebugEnabled(next)
      setEnabled(status.enabled)
      if (status.enabled) {
        const logs = await getDebugLogs()
        setEvents(logs.events)
      } else {
        setEvents([])
      }
    } catch {
      setEnabled(false)
      setEvents([])
    }
  }

  return (
    <div className="debug-dock">
      <div className="debug-dock__bar">
        <button
          type="button"
          className={`debug-dock__toggle ${enabled ? 'debug-dock__toggle--on' : 'debug-dock__toggle--off'}`}
          aria-pressed={enabled}
          onClick={() => void toggle()}
        >
          {enabled ? 'Debug Off' : 'Debug On'}
        </button>
      </div>
      {enabled && (
        <section className="debug-console" aria-label="debug console">
          {events.length === 0 ? (
            <p className="empty-hint">No debug events yet.</p>
          ) : (
            <ol>
              {[...events].reverse().map((item, index) => (
                <li key={`${item.stamp ?? item.at ?? 'event'}-${index}`} data-level={item.level}>
                  {formatDebugLine(item)}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  )
}
