import { useState } from 'react'
import { postDebugEvent, respondToApproval, streamTurn, verifyTurn, type TurnEvent } from '../lib/api'
import { newId } from '../lib/id'

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
        const stage = String(event.data.stage ?? '')
        setStatus(stage)
        void postDebugEvent({
          event: 'progress',
          message: stage,
          detail: { source: 'chat.sse' },
        }).catch(() => undefined)
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
        const message = String(event.data.message ?? 'something went wrong')
        setStatus(`Error: ${message}`)
        updateMessage(id, (m) => ({
          ...m,
          text: m.text.trim() ? m.text : message,
        }))
        void postDebugEvent({
          event: 'error',
          level: 'error',
          message,
          detail: { source: 'chat.sse' },
        }).catch(() => undefined)
      } else if (event.type === 'done') {
        if (event.data.conversation_id) {
          setConversationId(String(event.data.conversation_id))
        }
        if (event.data.turn_id) {
          const turnId = String(event.data.turn_id)
          updateMessage(id, (m) => ({ ...m, turnId }))
        }
        setStatus(null)
        void postDebugEvent({
          event: 'done',
          message: 'Turn finished',
          detail: {
            source: 'chat.sse',
            turn_id: event.data.turn_id,
            conversation_id: event.data.conversation_id,
          },
        }).catch(() => undefined)
      }
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || sending) return

    const userMessage = input
    const assistantId = newId()
    setMessages((prev) => [
      ...prev,
      { id: newId(), role: 'user', text: userMessage },
      { id: assistantId, role: 'assistant', text: '' },
    ])
    setInput('')
    setSending(true)
    setStatus(null)
    void postDebugEvent({
      event: 'submit',
      message: `Sending ${userMessage.length} characters`,
      detail: { source: 'chat.send', chars: userMessage.length },
    }).catch(() => undefined)

    try {
      await consumeEvents(streamTurn(conversationId, userMessage), assistantId)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to send message'
      setStatus(`Error: ${message}`)
      updateMessage(assistantId, (m) => ({
        ...m,
        text: m.text.trim() ? m.text : message,
      }))
      void postDebugEvent({
        event: 'error',
        level: 'error',
        message,
        detail: { source: 'chat.send' },
      }).catch(() => undefined)
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
    } catch (err) {
      const text = err instanceof Error ? err.message : 'Failed to continue the turn'
      setStatus(`Error: ${text}`)
      updateMessage(id, (m) => ({
        ...m,
        text: m.text.trim() ? m.text : text,
      }))
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
