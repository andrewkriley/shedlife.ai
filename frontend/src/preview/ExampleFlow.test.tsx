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

async function walkOnboarding(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Proxmox IP or API URL'), '192.0.2.10')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Proxmox Token ID'), 'root@pam!shed')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Proxmox Token Secret'), 'preview-secret')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  expect(screen.getByLabelText('Bridge')).toHaveValue('vmbr0')
  expect(screen.getByLabelText('Storage')).toHaveValue('local-lvm')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('API key'), 'sk-preview')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.type(screen.getByLabelText('Tenant name'), 'Riley Lab')
  await user.type(screen.getByLabelText('Tenant slug'), 'riley-lab')
  await user.click(screen.getByRole('button', { name: 'Continue' }))
  await user.click(screen.getByRole('button', { name: 'Validate' }))
  expect(screen.getByRole('heading', { name: 'Ready' })).toBeInTheDocument()
  expect(screen.getByLabelText('onboarding summary')).toHaveTextContent('Proxmox API')
  await user.click(screen.getByRole('button', { name: 'Finish' }))
}

describe('ExampleFlow', () => {
  it('walks setup, login, onboarding, and the chat workspace without API calls', async () => {
    const setup = vi.spyOn(api, 'getSetupStatus')
    const login = vi.spyOn(api, 'login')
    const user = userEvent.setup()
    render(<ExampleFlow />)

    expect(screen.getByText(/UI-only preview/)).toBeInTheDocument()
    await completeSetupAndLogin(user)
    expect(screen.getByRole('region', { name: 'Onboarding' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Foundations' })).toBeInTheDocument()
    expect(document.querySelector('.app-shell')).toHaveAttribute('data-layout', 'single-window')

    await walkOnboarding(user)
    expect(screen.getByLabelText('Message')).toBeInTheDocument()
    expect(screen.getByText('Riley Lab')).toBeInTheDocument()
    expect(screen.getByText('192.0.2.10')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Install the SSH key' }))
    expect(screen.getByText('Install the SSH key')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Approve' }))
    expect(screen.getByText(/ssh_key_installed passed/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(screen.getByText(/Independent verifier/)).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Issues' }))
    expect(screen.getByText(/predeploy-probe ntp_ok crashed/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Summary'), 'chat felt stuck')
    await user.type(screen.getByLabelText('Detail'), 'no reply after send')
    await user.click(screen.getByRole('button', { name: 'File issue' }))
    expect(screen.getByText(/chat felt stuck/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Settings' }))
    expect(screen.getByRole('group', { name: 'Change the model' })).toBeInTheDocument()
    expect(screen.getByText('bootstrap.intake')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Apply this model' }))
    expect(screen.getByText(/assigned to the selected assistant/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back to chat' }))
    expect(screen.getByText('Install the SSH key')).toBeInTheDocument()

    expect(setup).not.toHaveBeenCalled()
    expect(login).not.toHaveBeenCalled()
  })

  it('blocks an empty onboarding host and can restart the preview', async () => {
    const user = userEvent.setup()
    render(<ExampleFlow />)
    await completeSetupAndLogin(user)
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Proxmox host is required')
    await user.click(screen.getByRole('button', { name: 'Restart preview' }))
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })
})
