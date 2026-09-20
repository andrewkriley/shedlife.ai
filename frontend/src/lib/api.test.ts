import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamTurn } from './api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamTurn', () => {
  it('includes the HTTP detail when the turn stream fails to open', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        body: null,
        clone() {
          return this
        },
        async json() {
          return { detail: 'CSRF token missing' }
        },
        async text() {
          return '{"detail":"CSRF token missing"}'
        },
      }),
    )

    await expect(async () => {
      const iterator = streamTurn(null, 'hi')
      await iterator.next()
    }).rejects.toThrow('CSRF token missing')
  })

  it('yields a trailing SSE event when the stream ends without a blank line', async () => {
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: error\ndata: {"message":"boom"}'))
        controller.close()
      },
    })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: stream,
      }),
    )

    const events = []
    for await (const event of streamTurn(null, 'hi')) {
      events.push(event)
    }
    expect(events).toEqual([{ type: 'error', data: { message: 'boom' } }])
  })
})
