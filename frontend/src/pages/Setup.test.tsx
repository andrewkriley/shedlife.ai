import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Setup } from './Setup'
import * as api from '../lib/api'

describe('Setup', () => {
  it('submits the first operator account', async () => {
    const completeSetup = vi.spyOn(api, 'completeSetup').mockResolvedValue()
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<Setup onComplete={onComplete} />)

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple')
    await user.type(screen.getByLabelText('Confirm password'), 'correct-horse-battery-staple')
    await user.click(screen.getByRole('button', { name: 'Create operator' }))

    expect(completeSetup).toHaveBeenCalledWith({
      username: 'admin',
      password: 'correct-horse-battery-staple',
    })
    expect(onComplete).toHaveBeenCalled()
  })

  it('does not submit when the password fields do not match', async () => {
    const completeSetup = vi.spyOn(api, 'completeSetup').mockResolvedValue()
    const user = userEvent.setup()
    render(<Setup onComplete={() => {}} />)

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple')
    await user.type(screen.getByLabelText('Confirm password'), 'different-password')
    await user.click(screen.getByRole('button', { name: 'Create operator' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match')
    expect(completeSetup).not.toHaveBeenCalled()
  })

  it('does not collect an API key or Galileo on this gate', () => {
    render(<Setup onComplete={() => {}} />)
    expect(screen.queryByLabelText('API key')).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Galileo/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Provider')).not.toBeInTheDocument()
  })
})
