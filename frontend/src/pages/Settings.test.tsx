import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Settings } from './Settings'
import * as api from '../lib/api'

const baseSubAgents: api.SubAgentSetting[] = [
  {
    id: 'assist',
    macro_category: 'assist',
    description: 'General assistant',
    default_provider: 'anthropic',
    default_model: 'claude-haiku-4-5',
    provider: 'anthropic',
    model: 'claude-haiku-4-5',
    overridden: false,
  },
]

describe('Settings', () => {
  it('lists sub-agents with their current provider/model', async () => {
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue(baseSubAgents)
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })

    render(<Settings onClose={() => {}} />)

    expect(await screen.findByText(/assist/)).toBeInTheDocument()
    expect(screen.getByText(/anthropic\/claude-haiku-4-5/)).toBeInTheDocument()
    expect(screen.getByText(/\(default\)/)).toBeInTheDocument()
  })

  it('applies a model assignment to the selected sub-agents', async () => {
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue(baseSubAgents)
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'anthropic', model: 'claude-sonnet-5', overridden: true },
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    await screen.findByText(/assist/)
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Apply to selected' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], 'anthropic', 'claude-sonnet-5')
    expect(await screen.findByText(/\(override\)/)).toBeInTheDocument()
  })

  it('clears an override for the selected sub-agents', async () => {
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'openai', model: 'gpt-5', overridden: true },
    ])
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      baseSubAgents[0],
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    await screen.findByText(/\(override\)/)
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Clear override' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], null, null)
    expect(await screen.findByText(/\(default\)/)).toBeInTheDocument()
  })
})
