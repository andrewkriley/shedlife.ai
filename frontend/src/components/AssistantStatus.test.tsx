import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AssistantStatus } from './AssistantStatus'
import * as api from '../lib/api'

describe('AssistantStatus', () => {
  it('shows AI Assistant is Connected when health is ok and an agent is registered', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      {
        id: 'bootstrap.intake',
        macro_category: 'assist',
        description: 'Bootstrap intake',
        default_provider: 'anthropic',
        default_model: 'claude-haiku-4-5',
        provider: 'anthropic',
        model: 'claude-haiku-4-5',
        overridden: false,
      },
    ])

    render(<AssistantStatus />)

    expect(await screen.findByText('AI Assistant is Connected')).toBeInTheDocument()
    expect(screen.getByLabelText('assistant connection')).toHaveAttribute('data-state', 'connected')
  })

  it('shows disconnected when the health check fails', async () => {
    vi.spyOn(api, 'getHealth').mockRejectedValue(new Error('down'))
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([])

    render(<AssistantStatus />)

    expect(await screen.findByText('AI Assistant is disconnected')).toBeInTheDocument()
    expect(screen.getByLabelText('assistant connection')).toHaveAttribute('data-state', 'disconnected')
  })
})
