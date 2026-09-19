import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DebugDock } from './DebugDock'
import * as api from '../lib/api'

describe('DebugDock', () => {
  it('toggles debug on and shows the live console', async () => {
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: false })
    const setDebugEnabled = vi.spyOn(api, 'setDebugEnabled').mockResolvedValue({ enabled: true })
    vi.spyOn(api, 'getDebugLogs').mockResolvedValue({
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
    })

    const user = userEvent.setup()
    render(<DebugDock />)

    await user.click(await screen.findByRole('button', { name: 'Debug off' }))
    expect(setDebugEnabled).toHaveBeenCalledWith(true)
    expect(await screen.findByLabelText('debug console')).toBeInTheDocument()
    expect(screen.getByText(/anthropic rejected the key/)).toBeInTheDocument()
  })
})
