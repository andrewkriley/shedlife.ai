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

function mockSettingsApis(overrides?: {
  models?: Record<string, string[]>
  connection?: api.ConnectionStatus
  galileo?: api.GalileoSettings
}) {
  vi.spyOn(api, 'getHealth').mockResolvedValue({ status: 'ok' })
  vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue(baseSubAgents)
  vi.spyOn(api, 'getLiveModels').mockResolvedValue(
    overrides?.models ?? { anthropic: ['claude-sonnet-5'] },
  )
  vi.spyOn(api, 'getConnection').mockResolvedValue(
    overrides?.connection ?? {
      provider: 'anthropic',
      model: 'claude-haiku-4-5',
      configured: true,
    },
  )
  vi.spyOn(api, 'getGalileoSettings').mockResolvedValue(
    overrides?.galileo ?? {
      project: 'the-shed',
      host: '',
      log_stream: 'default',
      api_key_set: false,
      configured: false,
    },
  )
}

describe('Settings', () => {
  it('lists sub-agents with their current provider/model', async () => {
    mockSettingsApis()

    render(<Settings onClose={() => {}} />)

    expect(await screen.findByText('assist')).toBeInTheDocument()
    expect(screen.getByText('anthropic/claude-haiku-4-5')).toBeInTheDocument()
    expect(screen.getByText(/Using the default model/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Your assistants' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Change the model' })).toBeInTheDocument()
    expect(await screen.findByText(/AI Assistant is Connected/)).toBeInTheDocument()
    expect(screen.getAllByLabelText('Provider').length).toBe(1)
    expect(screen.getByRole('option', { name: 'OpenAI' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Anthropic' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save provider key' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Galileo' })).toBeInTheDocument()
    expect(await screen.findByLabelText('Project')).toHaveValue('the-shed')
    expect(screen.getByLabelText('Log stream')).toHaveValue('default')
  })

  it('saves a provider key from the connection block', async () => {
    mockSettingsApis({
      models: {
        anthropic: ['claude-haiku-4-5'],
        openai: ['gpt-4o'],
        gemini: ['gemini-2.5-flash'],
      },
    })
    const setProviderKey = vi.spyOn(api, 'setProviderKey').mockResolvedValue({ provider: 'openai' })

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    await user.selectOptions(screen.getAllByLabelText('Provider')[0], 'openai')
    await user.type(screen.getByLabelText('API key'), 'sk-test-openai')
    await user.click(screen.getByRole('button', { name: 'Save provider key' }))

    expect(setProviderKey).toHaveBeenCalledWith('openai', 'sk-test-openai')
    expect(await screen.findByText(/Saved the openai key/)).toBeInTheDocument()
  })

  it('preselects the only assistant and applies a model without an extra click', async () => {
    mockSettingsApis()
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'anthropic', model: 'claude-sonnet-5', overridden: true },
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    expect(await screen.findByRole('option', { name: 'claude-sonnet-5' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], 'anthropic', 'claude-sonnet-5')
    expect(await screen.findByText(/Custom model/)).toBeInTheDocument()
  })

  it('notifies the header immediately after applying a model', async () => {
    mockSettingsApis()
    vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'anthropic', model: 'claude-sonnet-5', overridden: true },
    ])
    const notify = vi.spyOn(api, 'notifyConnectionChanged')

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    expect(await screen.findByRole('option', { name: 'claude-sonnet-5' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))

    expect(notify).toHaveBeenCalled()
  })

  it('clears an override for the selected sub-agents', async () => {
    mockSettingsApis()
    vi.spyOn(api, 'getSubAgentSettings').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'openai', model: 'gpt-5', overridden: true },
    ])
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

  it('assigns a model for the live vendor even if the key picker is on another provider', async () => {
    mockSettingsApis({
      models: {
        anthropic: ['claude-haiku-4-5'],
        openai: ['gpt-4.1-mini', 'gpt-5'],
      },
      connection: { provider: 'openai', model: 'gpt-4.1-mini', configured: true },
    })
    const setModelAssignments = vi.spyOn(api, 'setModelAssignments').mockResolvedValue([
      { ...baseSubAgents[0], provider: 'openai', model: 'gpt-5', overridden: true },
    ])

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    await user.selectOptions(screen.getByLabelText('Provider'), 'anthropic')
    expect(screen.getByRole('option', { name: 'gpt-5' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'claude-haiku-4-5' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Model'), 'gpt-5')
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))

    expect(setModelAssignments).toHaveBeenCalledWith(['assist'], 'openai', 'gpt-5')
  })

  it('shows the API error when apply is rejected', async () => {
    mockSettingsApis({
      connection: { provider: 'openai', model: 'gpt-4.1-mini', configured: true },
      models: { openai: ['gpt-4.1-mini'], anthropic: ['claude-haiku-4-5'] },
    })
    vi.spyOn(api, 'setModelAssignments').mockRejectedValue(
      new Error('Chat is using openai. Save an anthropic key first, then assign that provider\'s model.'),
    )

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByRole('checkbox')).toBeChecked()
    expect(await screen.findByRole('option', { name: 'gpt-4.1-mini' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))

    expect(
      await screen.findByText(/Chat is using openai. Save an anthropic key first/),
    ).toBeInTheDocument()
  })

  it('loads and saves Galileo project, host, log stream, and API key', async () => {
    mockSettingsApis({
      galileo: {
        project: 'shed-lab',
        host: 'https://galileo.example.test',
        log_stream: 'bootstrap',
        api_key_set: true,
        configured: true,
      },
    })
    const setGalileoSettings = vi.spyOn(api, 'setGalileoSettings').mockResolvedValue({
      project: 'shed-lab',
      host: 'https://galileo.example.test',
      log_stream: 'live',
      api_key_set: true,
      configured: true,
    })

    const user = userEvent.setup()
    render(<Settings onClose={() => {}} />)

    expect(await screen.findByLabelText('Project')).toHaveValue('shed-lab')
    expect(screen.getByLabelText('Host')).toHaveValue('https://galileo.example.test')
    expect(screen.getByLabelText('Log stream')).toHaveValue('bootstrap')
    await user.clear(screen.getByLabelText('Log stream'))
    await user.type(screen.getByLabelText('Log stream'), 'live')
    await user.type(screen.getByLabelText('Galileo API key'), 'galileo-secret')
    await user.click(screen.getByRole('button', { name: 'Save Galileo settings' }))

    expect(setGalileoSettings).toHaveBeenCalledWith({
      project: 'shed-lab',
      host: 'https://galileo.example.test',
      log_stream: 'live',
      api_key: 'galileo-secret',
    })
    expect(await screen.findByText(/Galileo settings saved/)).toBeInTheDocument()
  })
})
