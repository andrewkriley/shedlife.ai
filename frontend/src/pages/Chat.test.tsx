import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Chat } from './Chat'
import * as api from '../lib/api'

describe('Chat', () => {
  it('renders the message input and send button', () => {
    render(<Chat />)
    expect(screen.getByLabelText('Message')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send' })).toBeInTheDocument()
  })

  it('shows the user message immediately and the streamed assistant response as it arrives', async () => {
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'progress', data: { stage: 'classify:done' } }
      yield { type: 'token', data: { text: 'Hello' } }
      yield { type: 'token', data: { text: ' there' } }
      yield { type: 'done', data: { turn_id: 't1', conversation_id: 'c1' } }
    })

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText(/hi/)).toBeInTheDocument()
    expect(await screen.findByText(/Hello there/)).toBeInTheDocument()
  })

  it('shows an error status if the stream reports one', async () => {
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'error', data: { message: 'something broke' } }
    })

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByRole('status')).toHaveTextContent('something broke')
  })
})
