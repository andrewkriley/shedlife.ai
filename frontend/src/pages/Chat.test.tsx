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

  it('keeps the composer visible and shows an empty-state hint before any messages', () => {
    render(<Chat />)
    expect(screen.getByText(/Ask the bootstrap assistant/)).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'composer' })).toBeInTheDocument()
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

  it('records debug events when a message is sent and the turn finishes', async () => {
    const postDebugEvent = vi.spyOn(api, 'postDebugEvent').mockResolvedValue()
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'progress', data: { stage: 'classify:done' } }
      yield { type: 'token', data: { text: 'ok' } }
      yield { type: 'done', data: { turn_id: 't1', conversation_id: 'c1' } }
    })

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    expect(await screen.findByText('ok')).toBeInTheDocument()

    expect(postDebugEvent).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'submit', message: 'Sending 2 characters' }),
    )
    expect(postDebugEvent).toHaveBeenCalledWith(
      expect.objectContaining({ event: 'progress', message: 'classify:done' }),
    )
    expect(postDebugEvent).toHaveBeenCalledWith(expect.objectContaining({ event: 'done' }))
  })

  it('lets the user verify a completed assistant turn and shows the result', async () => {
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'token', data: { text: 'Paris.' } }
      yield { type: 'done', data: { turn_id: 't1', conversation_id: 'c1' } }
    })
    vi.spyOn(api, 'verifyTurn').mockResolvedValue('This holds up — it answers the question.')

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'capital of France?')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText(/Paris/)

    await user.click(screen.getByRole('button', { name: 'Verify' }))

    expect(api.verifyTurn).toHaveBeenCalledWith('t1')
    expect(await screen.findByText(/This holds up/)).toBeInTheDocument()
  })

  it('shows an approval prompt when the turn pauses, and resumes on approve', async () => {
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      yield { type: 'token', data: { text: 'Working on it.' } }
      yield {
        type: 'approval_required',
        data: {
          turn_id: 't1',
          tool_name: 'confirm_create_firewall_policy',
          arguments: { rule: 'block all' },
          sub_agent_id: 'run.network',
        },
      }
    })
    vi.spyOn(api, 'respondToApproval').mockImplementation(async function* () {
      yield { type: 'token', data: { text: ' Done.' } }
      yield { type: 'done', data: { turn_id: 't1', conversation_id: 'c1' } }
    })

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'lock down the network')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText(/confirm_create_firewall_policy/)).toBeInTheDocument()
    expect(screen.getByText(/run\.network/)).toBeInTheDocument()
    // Not verifiable while a decision is pending.
    expect(screen.queryByRole('button', { name: 'Verify' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Approve' }))

    expect(api.respondToApproval).toHaveBeenCalledWith('t1', true)
    expect(await screen.findByText(/Working on it\. Done\./)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
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

  it('keeps the user message and shows a send failure on the assistant bubble', async () => {
    vi.spyOn(api, 'streamTurn').mockImplementation(async function* () {
      throw new Error('CSRF token missing')
    })
    vi.spyOn(api, 'postDebugEvent').mockResolvedValue()

    const user = userEvent.setup()
    render(<Chat />)

    await user.type(screen.getByLabelText('Message'), 'hi')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(document.querySelector('.message--user')).toHaveTextContent('hi')
    expect(await screen.findByRole('status')).toHaveTextContent('CSRF token missing')
    expect(document.querySelector('.message--assistant')).toHaveTextContent('CSRF token missing')
  })
})
