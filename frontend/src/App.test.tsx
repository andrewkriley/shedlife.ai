import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'
import type { FoundationsDocument } from './lib/api'

const foundations: FoundationsDocument = {
  version: 1,
  tenant: { name: 'Riley Lab', slug: 'riley-lab' },
  operator: { email: 'op@example.com' },
  proxmox: { host: '192.0.2.10', node: 'pve', ssh_key_fingerprint: null },
  network: { bridge: 'vmbr0', address: '', gateway: '', ntp: 'inherit' },
  storage: { pool: 'local-lvm' },
  domains: { intended: [] },
  intent: {
    gitlab: { mode: 'build' },
    infisical: { mode: 'build' },
    dns: { mode: 'greenfield' },
    k3s: { mode: 'build' },
  },
  probes: {},
}

describe('App', () => {
  it('shows the setup gate when no operator exists yet', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: true })
    render(<App />)
    expect(await screen.findByLabelText('API key')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })

  it('shows login once setup is complete', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: false })
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: false })
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.queryByLabelText('API key')).not.toBeInTheDocument()
    expect(document.querySelector('.app-frame')?.contains(document.querySelector('.debug-dock'))).toBe(true)
  })

  it('opens a single-window shell with a connected indicator and grouped review tabs', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: false })
    vi.spyOn(api, 'login').mockResolvedValue()
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
    vi.spyOn(api, 'getFoundations').mockResolvedValue(foundations)
    vi.spyOn(api, 'getIssues').mockResolvedValue([])
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ anthropic: ['claude-haiku-4-5'] })
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: false })

    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(document.querySelector('.app-shell')).toHaveAttribute('data-layout', 'single-window')
    expect(document.querySelector('.app-shell')?.contains(document.querySelector('.debug-dock'))).toBe(true)
    expect(await screen.findByText('AI Assistant is Connected')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Foundations' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Issues' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Tenant' })).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Issues' }))
    expect(await screen.findByRole('group', { name: 'File an issue' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('group', { name: 'Change the model' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to chat' }))
    expect(screen.getByLabelText('Message')).toBeInTheDocument()
  })

  it('keeps the chat transcript after opening and leaving Settings', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: false })
    vi.spyOn(api, 'login').mockResolvedValue()
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
    vi.spyOn(api, 'getFoundations').mockResolvedValue(foundations)
    vi.spyOn(api, 'getIssues').mockResolvedValue([])
    vi.spyOn(api, 'getLiveModels').mockResolvedValue({ openai: ['gpt-5.4'] })
    vi.spyOn(api, 'getDebugStatus').mockResolvedValue({ enabled: false })
    vi.spyOn(api, 'getConnection').mockResolvedValue({
      provider: 'openai',
      model: 'gpt-5.4',
      configured: true,
    })
    vi.spyOn(api, 'postDebugEvent').mockResolvedValue()
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'token', data: { text: 'Hello there' } }
      yield { type: 'done', data: { turn_id: 't1', conversation_id: 'c1' } }
    })

    const user = userEvent.setup()
    render(<App />)
    await user.type(await screen.findByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    await user.type(await screen.findByLabelText('Message'), 'keep me')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText('keep me')).toBeInTheDocument()
    expect(await screen.findByText('Hello there')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(await screen.findByRole('group', { name: 'Change the model' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Back to chat' }))
    expect(screen.getByText('keep me')).toBeInTheDocument()
    expect(screen.getByText('Hello there')).toBeInTheDocument()
  })
})
