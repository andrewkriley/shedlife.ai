import { useState } from 'react'
import { respondToApproval, streamTurn, verifyTurn, type TurnEvent } from '../lib/api'

interface PendingApproval {
  toolName: string
  arguments: Record<string, unknown>
  subAgentId: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  turnId?: string
  verifying?: boolean
  verification?: string
  pendingApproval?: PendingApproval
  responding?: boolean
}

export function Chat() {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  function updateMessage(id: string, updater: (m: Message) => Message) {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)))
  }

  // Shared by a fresh submission and a resume after approval — both are the
  // same SSE event shape (progress/token/approval_required/done), just
  // opened via a different endpoint.
  async function consumeEvents(iterator: AsyncGenerator<TurnEvent>, id: string) {
    for await (const event of iterator) {
      if (event.type === 'progress') {
        setStatus(String(event.data.stage ?? ''))
      } else if (event.type === 'token') {
        const chunk = String(event.data.text ?? '')
        updateMessage(id, (m) => ({ ...m, text: m.text + chunk }))
      } else if (event.type === 'approval_required') {
        const turnId = event.data.turn_id ? String(event.data.turn_id) : undefined
        updateMessage(id, (m) => ({
          ...m,
          turnId: turnId ?? m.turnId,
          pendingApproval: {
            toolName: String(event.data.tool_name ?? ''),
            arguments: (event.data.arguments as Record<string, unknown>) ?? {},
            subAgentId: String(event.data.sub_agent_id ?? ''),
          },
        }))
      } else if (event.type === 'error') {
        setStatus(`Error: ${String(event.data.message ?? 'something went wrong')}`)
      } else if (event.type === 'done') {
        if (event.data.conversation_id) {
          setConversationId(String(event.data.conversation_id))
        }
        if (event.data.turn_id) {
          const turnId = String(event.data.turn_id)
          updateMessage(id, (m) => ({ ...m, turnId }))
        }
        setStatus(null)
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || sending) return

    const userMessage = input
    const assistantId = crypto.randomUUID()
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: 'user', text: userMessage },
      { id: assistantId, role: 'assistant', text: '' },
    ])
    setInput('')
    setSending(true)
    setStatus(null)

    try {
      await consumeEvents(streamTurn(conversationId, userMessage), assistantId)
    } finally {
      setSending(false)
    }
  }

  async function handleApprove(id: string, approved: boolean) {
    const message = messages.find((m) => m.id === id)
    if (!message?.turnId) return

    updateMessage(id, (m) => ({ ...m, responding: true, pendingApproval: undefined }))
    setSending(true)
    setStatus(null)
    try {
      await consumeEvents(respondToApproval(message.turnId, approved), id)
    } finally {
      updateMessage(id, (m) => ({ ...m, responding: false }))
      setSending(false)
    }
  }

  async function handleVerify(id: string) {
    const message = messages.find((m) => m.id === id)
    if (!message?.turnId) return

    updateMessage(id, (m) => ({ ...m, verifying: true }))
    try {
      const result = await verifyTurn(message.turnId)
      updateMessage(id, (m) => ({ ...m, verifying: false, verification: result }))
    } catch {
      updateMessage(id, (m) => ({ ...m, verifying: false, verification: 'Verification failed.' }))
    }
  }

  return (
    <div className="chat-pane">
      <div className="message-list" role="log" aria-label="conversation">
        {messages.length === 0 && (
          <p className="message-list__empty">
            Ask the bootstrap assistant to collect foundations, validate them, or run a probe.
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} data-role={m.role} className={`message message--${m.role}`}>
            <span className="message__role">{m.role === 'user' ? 'You' : 'Shed'}</span>
            <p className="message__content">
              {m.text || (m.role === 'assistant' && sending ? 'thinking…' : '')}
            </p>
            {m.role === 'assistant' && m.pendingApproval && (
              <div data-role="approval-request" className="message__actions">
                <p>
                  <strong>{m.pendingApproval.subAgentId}</strong> wants to run{' '}
                  <code>{m.pendingApproval.toolName}</code> with{' '}
                  <code>{JSON.stringify(m.pendingApproval.arguments)}</code>
                </p>
                <button type="button" onClick={() => handleApprove(m.id, true)} disabled={m.responding}>
                  {m.responding ? 'Working…' : 'Approve'}
                </button>
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => handleApprove(m.id, false)}
                  disabled={m.responding}
                >
                  Decline
                </button>
              </div>
            )}
            {m.role === 'assistant' && m.turnId && !m.pendingApproval && (
              <div className="message__actions">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => handleVerify(m.id)}
                  disabled={m.verifying}
                >
                  {m.verifying ? 'Verifying…' : 'Verify'}
                </button>
                {m.verification && <p data-role="verification">{m.verification}</p>}
              </div>
            )}
          </div>
        ))}
      </div>
      {status && <p role="status">{status}</p>}
      <form className="composer" aria-label="composer" onSubmit={handleSubmit}>
        <label htmlFor="message" className="visually-hidden">
          Message
        </label>
        <input
          id="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
          placeholder="Ask something…"
        />
        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? 'Sending…' : 'Send'}
        </button>
      </form>
    </div>
  )
}
