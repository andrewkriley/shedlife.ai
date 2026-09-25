import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { DeployPhase } from './DeployPhase'

describe('DeployPhase', () => {
  it('starts at GitLab and returns to onboarding', async () => {
    const onBack = vi.fn()
    const user = userEvent.setup()
    render(<DeployPhase onBack={onBack} onFinished={() => {}} />)

    expect(screen.getByRole('region', { name: 'Deploy' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'GitLab' })).toBeInTheDocument()
    expect(screen.getByText('1 of 7')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(onBack).toHaveBeenCalled()
  })

  it('marks a platform and continues', async () => {
    const user = userEvent.setup()
    render(<DeployPhase onBack={() => {}} onFinished={() => {}} />)

    await user.click(screen.getByRole('button', { name: 'Provision GitLab' }))
    expect(screen.getByRole('heading', { name: 'Infisical · PKI, secrets' })).toBeInTheDocument()
    expect(screen.getByText('2 of 7')).toBeInTheDocument()
  })
})
