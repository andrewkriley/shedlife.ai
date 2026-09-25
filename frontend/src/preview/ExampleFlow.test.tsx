import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import * as api from '../lib/api'
import { ExampleFlow } from './ExampleFlow'

async function completeSetupAndLogin(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Username'), 'admin')
  await user.type(screen.getByLabelText('Password'), 'secret')
  await user.type(screen.getByLabelText('Confirm password'), 'secret')
  await user.click(screen.getByRole('button', { name: 'Create operator' }))
  await user.type(screen.getByLabelText('Username'), 'admin')
  await user.type(screen.getByLabelText('Password'), 'secret')
  await user.click(screen.getByRole('button', { name: 'Log in' }))
}

async function walkPrereq(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Address'), '192.0.2.10')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Proxmox Token ID'), 'root@pam!shed')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Proxmox Token Secret'), 'preview-secret')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Access key ID'), 'AKIAEXAMPLE')
  await user.type(screen.getByLabelText('Secret access key'), 'aws-secret')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('OpenRouter API key'), 'sk-or-preview')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Domain name'), 'lab.example')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Trusted SSH key'), 'ssh-ed25519 AAAA preview')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Cloudflare API token'), 'cf-preview')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
}

describe('ExampleFlow', () => {
  it('walks only Pre-req, one fact at a time, without API calls', async () => {
    const setup = vi.spyOn(api, 'getSetupStatus')
    const login = vi.spyOn(api, 'login')
    const user = userEvent.setup()
    render(<ExampleFlow />)

    expect(screen.getByText(/UI-only preview/)).toBeInTheDocument()
    await completeSetupAndLogin(user)

    expect(screen.getByRole('main', { name: 'Pre-req' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Proxmox IP' })).toBeInTheDocument()
    expect(screen.getByText('1 of 8')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Bootstrap' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Deploy' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Build' })).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()

    await walkPrereq(user)
    expect(screen.getByRole('heading', { name: 'Ready' })).toBeInTheDocument()
    expect(screen.getByText(/Bootstrap is next/)).toBeInTheDocument()
    expect(screen.getByLabelText('Pre-req review')).toHaveTextContent('192.0.2.10')
    expect(screen.getByLabelText('Pre-req review')).toHaveTextContent('OpenRouter API')
    expect(screen.getByLabelText('Pre-req review')).toHaveTextContent('Saved')

    await user.click(screen.getByRole('button', { name: /Proxmox IP/ }))
    expect(screen.getByRole('heading', { name: 'Proxmox IP' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: 'Ready' })).toBeInTheDocument()

    expect(setup).not.toHaveBeenCalled()
    expect(login).not.toHaveBeenCalled()
  })

  it('requires the current fact and can restart', async () => {
    const user = userEvent.setup()
    render(<ExampleFlow />)
    await completeSetupAndLogin(user)

    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Address is required')

    await user.type(screen.getByLabelText('Address'), '192.0.2.10')
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('heading', { name: 'Proxmox Token ID' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByRole('heading', { name: 'Proxmox IP' })).toBeInTheDocument()
    expect(screen.getByLabelText('Address')).toHaveValue('192.0.2.10')

    await user.click(screen.getByRole('button', { name: 'Restart preview' }))
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })
})
