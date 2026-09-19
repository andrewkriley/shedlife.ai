import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import * as api from './lib/api'

describe('App', () => {
  it('shows the setup gate when no operator exists yet', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: true })
    render(<App />)
    expect(await screen.findByLabelText('API key')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create operator' })).toBeInTheDocument()
  })

  it('shows login once setup is complete', async () => {
    vi.spyOn(api, 'getSetupStatus').mockResolvedValue({ needed: false })
    render(<App />)
    expect(await screen.findByRole('button', { name: 'Log in' })).toBeInTheDocument()
    expect(screen.queryByLabelText('API key')).not.toBeInTheDocument()
  })
})
