import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { FoundationsPanel } from './FoundationsPanel'
import * as api from '../lib/api'
import type { FoundationsDocument } from '../lib/api'

const baseDoc: FoundationsDocument = {
  version: 1,
  tenant: { name: 'Riley Lab', slug: '' },
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
  probes: { llm_key: { status: 'pass' } },
}

describe('FoundationsPanel', () => {
  it('renders schema state and shows validation field errors', async () => {
    vi.spyOn(api, 'getFoundations').mockResolvedValue(baseDoc)
    vi.spyOn(api, 'validateFoundations').mockResolvedValue({
      ok: false,
      errors: { 'tenant.slug': 'required' },
    })

    const user = userEvent.setup()
    render(<FoundationsPanel />)

    expect(await screen.findByDisplayValue('Riley Lab')).toBeInTheDocument()
    expect(screen.getByText(/llm_key: pass/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Tenant' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Proxmox' })).toBeInTheDocument()
    expect(screen.getByLabelText('Proxmox Token ID')).toBeInTheDocument()
    expect(screen.getByLabelText('Proxmox Token Secret')).toBeInTheDocument()
    expect(screen.getByLabelText('Tenant name')).toHaveAttribute('title', expect.stringContaining('Display name'))
    expect(screen.getByText('Tenant slug')).toHaveAttribute('title', expect.stringContaining('Short id'))
    expect(screen.getByRole('group', { name: 'Network' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Storage' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Domains' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Platform intent' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Validate' }))

    expect(await screen.findByText('required')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Field errors')
  })

  it('saves the schema through PUT', async () => {
    vi.spyOn(api, 'getFoundations').mockResolvedValue(baseDoc)
    const putFoundations = vi.spyOn(api, 'putFoundations').mockResolvedValue({
      ...baseDoc,
      tenant: { name: 'Riley Lab', slug: 'riley-lab' },
    })

    const user = userEvent.setup()
    render(<FoundationsPanel />)
    await screen.findByDisplayValue('Riley Lab')
    await user.type(screen.getByLabelText('Tenant slug'), 'riley-lab')
    await user.click(screen.getByRole('button', { name: 'Save schema' }))

    expect(putFoundations).toHaveBeenCalled()
    const saved = putFoundations.mock.calls[0][0]
    expect(saved.tenant.slug).toBe('riley-lab')
  })

  it('saves a proxmox API token from the foundations field', async () => {
    vi.spyOn(api, 'getFoundations').mockResolvedValue(baseDoc)
    const putFoundations = vi.spyOn(api, 'putFoundations').mockResolvedValue({
      ...baseDoc,
      proxmox: { ...baseDoc.proxmox, api_token_ref: 'local://proxmox/api_token', api_token_set: true },
    })

    const user = userEvent.setup()
    render(<FoundationsPanel />)
    await screen.findByDisplayValue('Riley Lab')
    await user.type(screen.getByLabelText('Proxmox Token ID'), 'root@pam!shed')
    await user.type(screen.getByLabelText('Proxmox Token Secret'), 'secret-token')
    await user.click(screen.getByRole('button', { name: 'Save schema' }))

    expect(putFoundations).toHaveBeenCalled()
    const saved = putFoundations.mock.calls[0][0]
    expect(saved.proxmox.api_token_id).toBe('root@pam!shed')
    expect(saved.proxmox.api_token_secret).toBe('secret-token')
    expect(saved.proxmox.api_token).toBeUndefined()
    expect(await screen.findByPlaceholderText(/Paste a new ID/)).toBeInTheDocument()
  })
})
