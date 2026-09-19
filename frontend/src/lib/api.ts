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

async function* consumeSseStream(response: Response): AsyncGenerator<TurnEvent> {
  if (!response.ok || !response.body) {
    throw new Error('Failed to open turn stream')
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
  yield* consumeSseStream(response)
}

// Resumes a turn paused by an `approval_required` event, per
// docs/spec/core-agentic-loop.md step 6d — same SSE shape as streamTurn
// (progress/token/approval_required/done), since the loop just keeps going
// from where it paused.
export async function* respondToApproval(
  turnId: string,
  approved: boolean,
): AsyncGenerator<TurnEvent> {
  const response = await fetch(`/api/turns/${turnId}/approvals`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': readCsrfCookie(),
    },
    body: JSON.stringify({ approved }),
  })
  yield* consumeSseStream(response)
}

export async function verifyTurn(turnId: string): Promise<string> {
  const response = await fetch(`/api/turns/${turnId}/verify`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'x-csrf-token': readCsrfCookie() },
  })
  if (!response.ok) {
    throw new Error('Verification failed')
  }
  const body: { result: string } = await response.json()
  return body.result
}

export interface SubAgentSetting {
  id: string
  macro_category: string
  description: string
  default_provider: string
  default_model: string
  provider: string
  model: string
  overridden: boolean
}

export async function getSubAgentSettings(): Promise<SubAgentSetting[]> {
  const response = await fetch('/api/settings/sub-agents', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load sub-agent settings')
  }
  return response.json()
}

export async function getLiveModels(): Promise<Record<string, string[]>> {
  const response = await fetch('/api/settings/models', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load live models')
  }
  return response.json()
}

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch('/api/health', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load health')
  }
  return response.json()
}

export async function getSetupStatus(): Promise<{ needed: boolean }> {
  const response = await fetch('/api/setup/status', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load setup status')
  }
  return response.json()
}

export async function completeSetup(body: {
  email: string
  password: string
  provider: string
  api_key: string
  galileo_api_key?: string
  galileo_console_url?: string
}): Promise<void> {
  const response = await fetch('/api/setup', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = 'Setup failed'
    try {
      const payload: { detail?: string } = await response.json()
      if (payload.detail) detail = payload.detail
    } catch {
      // keep default
    }
    throw new Error(detail)
  }
}

export interface FoundationsDocument {
  version: number
  tenant: { name: string; slug: string }
  operator: { email: string }
  proxmox: { host: string; node: string; ssh_key_fingerprint: string | null }
  network: { bridge: string; address: string; gateway: string; ntp: string }
  storage: { pool: string }
  domains: { intended: string[] }
  intent: Record<string, { mode: string; url?: string }>
  probes: Record<string, { status: string; at?: string; detail?: string }>
}

export async function getFoundations(): Promise<FoundationsDocument> {
  const response = await fetch('/api/foundations', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load foundations')
  }
  return response.json()
}

export async function putFoundations(document: FoundationsDocument): Promise<FoundationsDocument> {
  const response = await fetch('/api/foundations', {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': readCsrfCookie(),
    },
    body: JSON.stringify({ document }),
  })
  if (!response.ok) {
    throw new Error('Failed to save foundations')
  }
  return response.json()
}

export async function validateFoundations(): Promise<{ ok: boolean; errors: Record<string, string> }> {
  const response = await fetch('/api/foundations/validate', {
    method: 'POST',
    credentials: 'include',
    headers: { 'x-csrf-token': readCsrfCookie() },
  })
  if (!response.ok) {
    throw new Error('Failed to validate foundations')
  }
  return response.json()
}

export async function exportFoundations(): Promise<string> {
  const response = await fetch('/api/foundations/export', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to export foundations')
  }
  const body: { yaml: string } = await response.json()
  return body.yaml
}

export async function runProbe(probeId: string): Promise<{ status: string; detail: string }> {
  const response = await fetch(`/api/probes/${probeId}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'x-csrf-token': readCsrfCookie() },
  })
  if (!response.ok) {
    throw new Error('Failed to run probe')
  }
  return response.json()
}

export interface LocalIssue {
  id: string
  classification: string
  summary: string
  detail: string
  source: string
  filed_externally: string | null
  created_at: string
}

export async function getIssues(): Promise<LocalIssue[]> {
  const response = await fetch('/api/issues', { credentials: 'include' })
  if (!response.ok) {
    throw new Error('Failed to load issues')
  }
  return response.json()
}

export async function fileIssue(body: {
  summary: string
  detail: string
  classification?: string
}): Promise<LocalIssue> {
  const response = await fetch('/api/issues', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': readCsrfCookie(),
    },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error('Failed to file issue')
  }
  return response.json()
}

export async function setModelAssignments(
  subAgentIds: string[],
  provider: string | null,
  model: string | null,
): Promise<SubAgentSetting[]> {
  const response = await fetch('/api/settings/model-assignments', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'x-csrf-token': readCsrfCookie(),
    },
    body: JSON.stringify({ sub_agent_ids: subAgentIds, provider, model }),
  })
  if (!response.ok) {
    throw new Error('Failed to update model assignments')
  }
  return response.json()
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
