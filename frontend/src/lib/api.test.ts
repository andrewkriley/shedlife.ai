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
})
