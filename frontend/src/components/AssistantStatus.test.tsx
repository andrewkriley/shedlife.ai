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

  it('names the active provider and model when a key is configured', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      {
        id: 'bootstrap.intake',
        macro_category: 'assist',
        description: 'Bootstrap intake',
        default_provider: 'openai',
        default_model: 'gpt-5.4',
        provider: 'openai',
        model: 'gpt-5.4',
        overridden: false,
      },
    ])
    vi.spyOn(api, 'getConnection').mockResolvedValue({
      provider: 'openai',
      model: 'gpt-5.4',
      configured: true,
    })

    render(<AssistantStatus />)

    expect(
      await screen.findByText('AI Assistant is Connected · openai · gpt-5.4'),
    ).toBeInTheDocument()
  })

  it('refreshes the named model when the connection changes', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      {
        id: 'bootstrap.intake',
        macro_category: 'assist',
        description: 'Bootstrap intake',
        default_provider: 'openai',
        default_model: 'gpt-5.4',
        provider: 'openai',
        model: 'gpt-5.4',
        overridden: false,
      },
    ])
    const getConnection = vi.spyOn(api, 'getConnection')
    getConnection.mockResolvedValueOnce({
      provider: 'openai',
      model: 'gpt-5.4',
      configured: true,
    })
    getConnection.mockResolvedValue({
      provider: 'openai',
      model: 'gpt-5.4-mini',
      configured: true,
    })

    render(<AssistantStatus />)

    expect(
      await screen.findByText('AI Assistant is Connected · openai · gpt-5.4'),
    ).toBeInTheDocument()

    window.dispatchEvent(new Event(api.CONNECTION_CHANGED_EVENT))

    expect(
      await screen.findByText('AI Assistant is Connected · openai · gpt-5.4-mini'),
    ).toBeInTheDocument()
  })

  it('shows disconnected when the health check fails', async () => {
    vi.spyOn(api, 'getHealth').mockRejectedValue(new Error('down'))
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([])

    render(<AssistantStatus />)

    expect(await screen.findByText('AI Assistant is disconnected')).toBeInTheDocument()
    expect(screen.getByLabelText('assistant connection')).toHaveAttribute('data-state', 'disconnected')
  })
})
