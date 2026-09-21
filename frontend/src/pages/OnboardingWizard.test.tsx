import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { OnboardingWizard } from './OnboardingWizard'
import * as api from '../lib/api'

const emptyStatus: api.OnboardingStatus = {
  needed: true,
  tenant: { name: '', slug: '' },
  proxmox: { host: '', node: '', api_token_id: '', api_token_set: false },
  network: { bridge: '' },
  storage: { pool: '' },
  provider: { vendor: null, api_key_set: false },
  intent: {
    mode: 'build',
    services: {
      gitlab: { mode: 'build', url: '' },
      infisical: { mode: 'build', url: '' },
      dns: { mode: 'greenfield', url: '' },
      k3s: { mode: 'build', url: '' },
    },
  },
  probes: {},
}

describe('OnboardingWizard', () => {
  it('walks the minimum steps and shows a summary', async () => {
    vi.spyOn(api, 'getOnboardingStatus').mockResolvedValue(emptyStatus)
    const postProxmox = vi.spyOn(api, 'postOnboardingProxmox').mockImplementation(async (body) => ({
      ...emptyStatus,
      proxmox: {
        host: body.host || '192.0.2.10',
        node: 'pve',
        api_token_id: body.api_token_id || '',
        api_token_set: Boolean(body.discover || body.api_token_id),
      },
      network: { bridge: 'vmbr0' },
      discovery: body.discover
        ? { version: '8.3', nodes: ['pve'], bridges: ['vmbr0'], pools: ['local-lvm'] }
        : null,
    }))
    vi.spyOn(api, 'postOnboardingProvider').mockResolvedValue({
      provider: { vendor: 'anthropic', api_key_set: true },
    })
    vi.spyOn(api, 'postOnboardingTenant').mockResolvedValue({
      ...emptyStatus,
      needed: false,
      tenant: { name: 'Riley Lab', slug: 'riley-lab' },
      proxmox: { host: '192.0.2.10', node: 'pve', api_token_id: 'root@pam!shed', api_token_set: true },
      provider: { vendor: 'anthropic', api_key_set: true },
    })
    vi.spyOn(api, 'postOnboardingIntent').mockResolvedValue({
      ...emptyStatus,
      needed: false,
      tenant: { name: 'Riley Lab', slug: 'riley-lab' },
      proxmox: { host: '192.0.2.10', node: 'pve', api_token_id: 'root@pam!shed', api_token_set: true },
      provider: { vendor: 'anthropic', api_key_set: true },
      intent: { mode: 'build', services: emptyStatus.intent.services },
    })
    vi.spyOn(api, 'postOnboardingComplete').mockResolvedValue({
      ok: true,
      needed: false,
      checks: [
        { id: 'tenant', label: 'Tenant', status: 'pass', detail: 'Riley Lab (riley-lab)' },
        { id: 'proxmox_api', label: 'proxmox api', status: 'pass', detail: 'HTTP 200' },
      ],
      status: {
        ...emptyStatus,
        needed: false,
        tenant: { name: 'Riley Lab', slug: 'riley-lab' },
      },
    })
    const onFinished = vi.fn()
    const user = userEvent.setup()
    render(<OnboardingWizard onFinished={onFinished} />)

    await user.type(await screen.findByLabelText('Proxmox IP or API URL'), '192.0.2.10')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(postProxmox).toHaveBeenCalledWith({ host: '192.0.2.10' })

    await user.type(await screen.findByLabelText('Proxmox Token ID'), 'root@pam!shed')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await user.type(await screen.findByLabelText('Proxmox Token Secret'), 'secret-token')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(postProxmox).toHaveBeenCalledWith({
      api_token_id: 'root@pam!shed',
      api_token_secret: 'secret-token',
      discover: true,
    })

    await user.type(await screen.findByLabelText('API key'), 'sk-ant-api03-test')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    await user.type(await screen.findByLabelText('Tenant name'), 'Riley Lab')
    await user.type(screen.getByLabelText('Tenant slug'), 'riley-lab')
    await user.click(screen.getByRole('button', { name: 'Continue' }))

    expect(screen.getByLabelText(/Fresh install \(no adoption\)/)).toBeChecked()
    await user.click(screen.getByRole('button', { name: 'Validate' }))

    expect(await screen.findByRole('heading', { name: 'Ready' })).toBeInTheDocument()
    const summary = screen.getByRole('list', { name: 'onboarding summary' })
    expect(summary.textContent).toContain('Tenant')
    expect(summary.textContent).toContain('pass')
    await user.click(screen.getByRole('button', { name: 'Back to chat' }))
    expect(onFinished).toHaveBeenCalled()
  })

  it('pre-fills saved values on a re-run', async () => {
    vi.spyOn(api, 'getOnboardingStatus').mockResolvedValue({
      ...emptyStatus,
      needed: false,
      tenant: { name: 'Riley Lab', slug: 'riley-lab' },
      proxmox: { host: '192.0.2.10', node: 'pve', api_token_id: 'root@pam!shed', api_token_set: true },
      provider: { vendor: 'openai', api_key_set: true },
    })
    render(<OnboardingWizard onFinished={() => {}} />)
    expect(await screen.findByLabelText('Proxmox IP or API URL')).toHaveValue('192.0.2.10')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByLabelText('Proxmox Token ID')).toHaveValue('root@pam!shed')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Continue' }))
    expect(await screen.findByLabelText('Proxmox Token Secret')).toBeInTheDocument()
    expect(screen.getByText('Token ID: root@pam!shed')).toBeInTheDocument()
    expect(screen.getByText(/Token secret is saved/)).toBeInTheDocument()
  })
})
