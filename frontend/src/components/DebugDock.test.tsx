import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DebugDock } from './DebugDock'
import { formatDebugLine } from '../lib/debugTime'
import * as api from '../lib/api'

const sampleLogs = {
  enabled: true,
  events: [
    {
      at: '2026-09-20T00:00:00Z',
      stamp: '2026-09-20 10:00:00 UTC+10',
      level: 'error',
      source: 'provider',
      event: 'error',
      message: 'anthropic rejected the key',
    },
  ],
}

describe('DebugDock', () => {
  it('toggles debug on and shows the live console', async () => {
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: false })
    const setDebugEnabled = vi.spyOn(api, 'setDebugEnabled').mockResolvedValue({ enabled: true })
    vi.spyOn(api, 'getDebugLogs').mockResolvedValue(sampleLogs)

    const user = userEvent.setup()
    render(<DebugDock />)

    const toggle = await screen.findByRole('button', { name: 'Debug off' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    expect(toggle).toHaveClass('debug-dock__toggle--off')
    expect(screen.queryByLabelText('debug console')).not.toBeInTheDocument()

    await user.click(toggle)
    expect(setDebugEnabled).toHaveBeenCalledWith(true)
    expect(await screen.findByRole('button', { name: 'Debug on' })).toHaveClass('debug-dock__toggle--on')
    expect(await screen.findByLabelText('debug console')).toBeInTheDocument()
    expect(screen.getByText(/anthropic rejected the key/)).toBeInTheDocument()
    const line = screen.getByRole('listitem')
    expect(line.textContent).toBe(formatDebugLine(sampleLogs.events[0]))
    expect(line.textContent?.startsWith('2026-09-20 10:00:00 UTC+10')).toBe(true)
  })

  it('still prints a server stamp when at is omitted', async () => {
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: true })
    vi.spyOn(api, 'getDebugLogs').mockResolvedValue({
      enabled: true,
      events: [
        {
          stamp: '2026-09-21 16:51:03 UTC+10',
          level: 'info',
          source: 'http',
          event: 'request',
          message: 'GET /settings/connection → 200 (1ms)',
        },
      ],
    })

    render(<DebugDock />)
    const line = await screen.findByRole('listitem')
    expect(line.textContent).toBe(
      '2026-09-21 16:51:03 UTC+10  http · request  GET /settings/connection → 200 (1ms)',
    )
  })

  it('lists the newest debug event first', async () => {
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: true })
    vi.spyOn(api, 'getDebugLogs').mockResolvedValue({
      enabled: true,
      events: [
        {
          at: '2026-09-20T00:00:00Z',
          level: 'info',
          source: 'turn',
          event: 'start',
          message: 'older turn started',
        },
        {
          at: '2026-09-20T00:00:02Z',
          level: 'info',
          source: 'llm',
          event: 'done',
          message: 'newest model returned',
        },
      ],
    })

    render(<DebugDock />)
    const items = await screen.findAllByRole('listitem')
    expect(items[0]).toHaveTextContent('newest model returned')
    expect(items[1]).toHaveTextContent('older turn started')
  })

  it('shows logs when debug is already on and hides them when turned off', async () => {
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: true })
    vi.spyOn(api, 'getDebugLogs').mockResolvedValue(sampleLogs)
    const setDebugEnabled = vi.spyOn(api, 'setDebugEnabled').mockResolvedValue({ enabled: false })

    const user = userEvent.setup()
    render(<DebugDock />)

    expect(await screen.findByRole('button', { name: 'Debug on' })).toHaveClass('debug-dock__toggle--on')
    expect(await screen.findByLabelText('debug console')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Debug on' }))
    expect(setDebugEnabled).toHaveBeenCalledWith(false)
    expect(await screen.findByRole('button', { name: 'Debug off' })).toHaveClass('debug-dock__toggle--off')
    expect(screen.queryByLabelText('debug console')).not.toBeInTheDocument()
  })
})
