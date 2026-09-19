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
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue(baseSubAgents)
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })

    render(<Settings onClose={() => {}} />)

    expect(await screen.findByText('assist')).toBeInTheDocument()
    expect(screen.getByText('anthropic/claude-haiku-4-5')).toBeInTheDocument()
    expect(screen.getByText(/Using the default model/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Your assistants' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Change the model' })).toBeInTheDocument()
    expect(await screen.findByText('AI Assistant is Connected')).toBeInTheDocument()
  })

  it('preselects the only assistant and applies a model without an extra click', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue(baseSubAgents)
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'anthropic', model: 'claude-sonnet-5', overridden: true },
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], 'anthropic', 'claude-sonnet-5')
    expect(await screen.findByText(/Custom model/)).toBeInTheDocument()
  })

  it('clears an override for the selected sub-agents', async () => {
    vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'openai', model: 'gpt-5', overridden: true },
    ])
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-sonnet-5'] })
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      baseSubAgents[0],
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Use default model' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], null, null)
    expect(await screen.findByText(/Using the default model/)).toBeInTheDocument()
  })
})
