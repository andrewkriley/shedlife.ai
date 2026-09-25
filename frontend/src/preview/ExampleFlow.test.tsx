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

describe('ExampleFlow', () => {
  it('shows the full scrolling checklist without API calls', async () => {
    const setup = vi.spyOn(api, 'getSetupStatus')
    const login = vi.spyOn(api, 'login')
    const user = userEvent.setup()
    render(<ExampleFlow />)

    expect(screen.getByText(/UI-only preview/)).toBeInTheDocument()
    await completeSetupAndLogin(user)

    expect(screen.getByRole('main', { name: 'checklist' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Pre-req' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Bootstrap' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Deploy' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Build' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'OpenRouter API' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Trusted SSH key' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Cloudflare API' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'K3S' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'LiteLLM gateway' })).toBeInTheDocument()
    expect(screen.getByText(/0 of 21/)).toBeInTheDocument()

    await user.type(screen.getByLabelText('Address'), '192.0.2.10')
    await user.click(screen.getByRole('checkbox', { name: 'Proxmox IP' }))
    expect(screen.getByRole('checkbox', { name: 'Proxmox IP' })).toBeChecked()
    expect(screen.getByRole('main', { name: 'checklist' })).toHaveTextContent(/1 of 21/)

    await user.click(screen.getByRole('checkbox', { name: 'Validation checks' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Finish Pre-req first.')
    expect(screen.getByRole('checkbox', { name: 'Validation checks' })).not.toBeChecked()

    expect(setup).not.toHaveBeenCalled()
    expect(login).not.toHaveBeenCalled()
  })

  it('requires a value before checking a field and can restart', async () => {
    const user = userEvent.setup()
    render(<ExampleFlow />)
    await completeSetupAndLogin(user)

    await user.click(screen.getByRole('checkbox', { name: 'Proxmox IP' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Address is required')
    expect(screen.getByRole('checkbox', { name: 'Proxmox IP' })).not.toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Restart preview' }))
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })
})
