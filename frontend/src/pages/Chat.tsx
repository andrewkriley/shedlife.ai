import { useState } from 'react'
import { streamTurn, verifyTurn } from '../lib/api'

interface Message {
  role: 'user' | 'assistant'
  text: string
  turnId?: string
  verifying?: boolean
  verification?: string
}

export function Chat({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [status, setStatus] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || sending) return

    const userMessage = input
    setMessages((prev) => [...prev, { role: 'user', text: userMessage }])
    setInput('')
    setSending(true)
    setStatus(null)

    let assistantText = ''
    setMessages((prev) => [...prev, { role: 'assistant', text: '' }])

    try {
      for await (const event of streamTurn(conversationId, userMessage)) {
        if (event.type === 'progress') {
          setStatus(String(event.data.stage ?? ''))
        } else if (event.type === 'token') {
          assistantText += String(event.data.text ?? '')
          setMessages((prev) => [...prev.slice(0, -1), { role: 'assistant', text: assistantText }])
        } else if (event.type === 'error') {
          setStatus(`Error: ${String(event.data.message ?? 'something went wrong')}`)
        } else if (event.type === 'done') {
          if (event.data.conversation_id) {
            setConversationId(String(event.data.conversation_id))
          }
          if (event.data.turn_id) {
            const turnId = String(event.data.turn_id)
            setMessages((prev) => [...prev.slice(0, -1), { ...prev[prev.length - 1], turnId }])
          }
          setStatus(null)
        }
      }
    } finally {
      setSending(false)
    }
  }

  async function handleVerify(index: number) {
    const message = messages[index]
    if (!message.turnId) return

    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, verifying: true } : m)))
    try {
      const result = await verifyTurn(message.turnId)
      setMessages((prev) =>
        prev.map((m, i) => (i === index ? { ...m, verifying: false, verification: result } : m)),
      )
    } catch {
      setMessages((prev) =>
        prev.map((m, i) =>
          i === index ? { ...m, verifying: false, verification: 'Verification failed.' } : m,
        ),
      )
    }
  }

  return (
    <div>
      <h1>The Shed</h1>
      <button type="button" onClick={onOpenSettings}>
        Settings
      </button>
      <div role="log" aria-label="conversation">
        {messages.map((m, i) => (
          <div key={i} data-role={m.role}>
            <p>
              <strong>{m.role === 'user' ? 'You' : 'Shed'}:</strong> {m.text}
            </p>
            {m.role === 'assistant' && m.turnId && (
              <>
                <button type="button" onClick={() => handleVerify(i)} disabled={m.verifying}>
                  {m.verifying ? 'Verifying…' : 'Verify'}
                </button>
                {m.verification && <p data-role="verification">{m.verification}</p>}
              </>
            )}
          </div>
        ))}
      </div>
      {status && <p role="status">{status}</p>}
      <form onSubmit={handleSubmit}>
        <label htmlFor="message">Message</label>
        <input
          id="message"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={sending}
        />
        <button type="submit" disabled={sending}>
          Send
        </button>
      </form>
    </div>
  )
}
