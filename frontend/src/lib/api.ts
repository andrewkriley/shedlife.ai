// Talks to the backend over cookie-based sessions (see docs/spec/auth.md) —
// `credentials: 'include'` on every call, no Authorization header to manage.
//
// Turn streaming uses `fetch()` with a manually-parsed text/event-stream
// body, not the native `EventSource` object: EventSource can only issue GET
// requests, and submitting a turn is a POST (it carries the message body).
// Cookies still ride along automatically either way — that's independent of
// which of the two transports is used.

export interface TurnEvent {
  type: 'progress' | 'token' | 'approval_required' | 'error' | 'done'
  data: Record<string, unknown>
}

// Double-submit CSRF: the backend sets a non-HttpOnly `shed_csrf` cookie on
// login specifically so page JS can read it and echo it back as a header on
// state-changing requests (see docs/spec/auth.md). Confirmed live: without
// this, POST /turns 403s — the cookie alone was never enough on its own.
function readCsrfCookie(): string {
  const match = document.cookie.match(/(?:^|;\s*)shed_csrf=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!response.ok) {
    throw new Error('Login failed')
  }
}

export async function* streamTurn(
  conversationId: string | null,
  message: string,
): AsyncGenerator<TurnEvent> {
  const response = await fetch('/api/turns', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': readCsrfCookie(),
    },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!response.ok || !response.body) {
    throw new Error('Failed to start turn')
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    // The server emits \r\n line endings (valid per the SSE spec — Starlette's
    // own choice, confirmed live by inspecting the raw stream). \r\n\r\n never
    // contains the substring \n\n, so splitting on a bare '\n\n' silently
    // matched nothing at all: the buffer just grew forever and no event was
    // ever parsed out, with no error anywhere — the fetch still completed
    // normally. Normalizing line endings first is the fix.
    buffer += value.replace(/\r\n/g, '\n')

    const events = buffer.split('\n\n')
    buffer = events.pop() ?? ''

    for (const raw of events) {
      const event = parseSseEvent(raw)
      if (event) yield event
    }
  }
}

function parseSseEvent(raw: string): TurnEvent | null {
  const lines = raw.split('\n')
  let eventType = 'message'
  let data = ''
  for (const line of lines) {
    if (line.startsWith('event:')) eventType = line.slice('event:'.length).trim()
    if (line.startsWith('data:')) data += line.slice('data:'.length).trim()
  }
  if (!data) return null
  try {
    return { type: eventType as TurnEvent['type'], data: JSON.parse(data) }
  } catch {
    return null
  }
}
