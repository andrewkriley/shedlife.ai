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
  it('walks the quieter overview path without API calls', async () => {
    const setup = vi.spyOn(api, 'getSetupStatus')
    const login = vi.spyOn(api, 'login')
    const user = userEvent.setup()
    render(<ExampleFlow />)

    expect(screen.getByText(/UI-only preview/)).toBeInTheDocument()
    await completeSetupAndLogin(user)

    expect(screen.getByRole('main', { name: 'journey home' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Pre-req/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Bootstrap/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Deploy/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Build/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Pre-req/ }))
    expect(screen.getByRole('heading', { name: 'Pre-req' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /OpenRouter API/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Trusted SSH key/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cloudflare API/ })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^Proxmox IP/ }))
    await user.type(screen.getByLabelText('Address'), '192.0.2.10')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByRole('heading', { name: 'Pre-req' })).toBeInTheDocument()
    expect(screen.getByText('192.0.2.10')).toBeInTheDocument()
    expect(screen.getByRole('main', { name: 'Pre-req' })).toHaveTextContent(/1 of 8/)

    await user.click(screen.getByRole('button', { name: 'The Shed' }))
    await user.click(screen.getByRole('button', { name: /Bootstrap/ }))
    await user.click(screen.getByRole('button', { name: /^Validation checks/ }))
    await user.click(screen.getByRole('button', { name: 'Run checks' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Finish Pre-req first.')

    expect(setup).not.toHaveBeenCalled()
    expect(login).not.toHaveBeenCalled()
  })

  it('can switch to one-at-a-time and restart the preview', async () => {
    const user = userEvent.setup()
    render(<ExampleFlow />)
    await completeSetupAndLogin(user)

    await user.click(screen.getByRole('tab', { name: 'One at a time' }))
    expect(screen.getByRole('heading', { name: 'Proxmox IP' })).toBeInTheDocument()
    expect(screen.getByText(/1 of 21/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Continue' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Address is required')

    await user.click(screen.getByRole('button', { name: 'Restart preview' }))
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })
})
