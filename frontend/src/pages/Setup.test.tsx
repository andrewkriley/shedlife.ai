import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Setup } from './Setup'
import * as api from '../lib/api'

describe('Setup', () => {
  it('submits provider, API key, and the first operator account', async () => {
    const completeSetup = vi.spyOn(api, 'completeSetup').mockResolvedValue()
    const onComplete = vi.fn()
    const user = userEvent.setup()
    render(<Setup onComplete={onComplete} />)

    await user.selectOptions(screen.getByLabelText('Provider'), 'anthropic')
    await user.type(screen.getByLabelText('API key'), 'sk-ant-api03-test')
    await user.type(screen.getByLabelText('Email'), 'op@example.com')
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple')
    await user.click(screen.getByRole('button', { name: 'Create operator' }))

    expect(completeSetup).toHaveBeenCalledWith({
      email: 'op@example.com',
      password: 'correct-horse-battery-staple',
      provider: 'anthropic',
      api_key: 'sk-ant-api03-test',
      galileo_api_key: undefined,
      galileo_console_url: undefined,
    })
    expect(onComplete).toHaveBeenCalled()
  })

  it('shows a subscription rejection on the gate', async () => {
    vi.spyOn(api, 'completeSetup').mockRejectedValue(
      new Error('A Claude subscription will not work. Use an Anthropic, OpenAI, or Gemini API key.'),
    )
    const user = userEvent.setup()
    render(<Setup onComplete={() => {}} />)

    await user.type(screen.getByLabelText('API key'), 'claude subscription')
    await user.type(screen.getByLabelText('Email'), 'op@example.com')
    await user.type(screen.getByLabelText('Password'), 'x')
    await user.click(screen.getByRole('button', { name: 'Create operator' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('subscription will not work')
  })
})
