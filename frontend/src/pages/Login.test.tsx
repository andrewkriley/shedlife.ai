import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Login } from './Login'
import * as api from '../lib/api'

describe('Login', () => {
  it('accepts username admin, not an email field', async () => {
    const login = vi.spyOn(api, 'login').mockResolvedValue()
    const onLoggedIn = vi.fn()
    const user = userEvent.setup()
    render(<Login onLoggedIn={onLoggedIn} />)

    const field = screen.getByLabelText('Username')
    expect(field).toHaveAttribute('type', 'text')
    expect(field).not.toHaveAttribute('type', 'email')
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()

    await user.type(field, 'admin')
    await user.type(screen.getByLabelText('Password'), 'once-only')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(login).toHaveBeenCalledWith('admin', 'once-only')
    expect(onLoggedIn).toHaveBeenCalled()
  })
})
