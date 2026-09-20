import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DebugDock } from './DebugDock'
import * as api from '../lib/api'

const sampleLogs = {
  enabled: true,
  events: [
    {
      at: '2026-09-20T00:00:00Z',
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
