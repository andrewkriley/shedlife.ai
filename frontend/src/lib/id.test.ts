import { afterEach, describe, expect, it, vi } from 'vitest'
import { newId } from './id'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('newId', () => {
  it('uses crypto.randomUUID when the context allows it', () => {
    vi.stubGlobal('crypto', {
      randomUUID: () => '11111111-1111-1111-1111-111111111111',
    })
    expect(newId()).toBe('11111111-1111-1111-1111-111111111111')
  })

  it('still returns a UUID when randomUUID is missing (LAN HTTP)', () => {
    vi.stubGlobal('crypto', {
      getRandomValues(bytes: Uint8Array) {
        bytes.fill(7)
        return bytes
      },
    })
    const id = newId()
    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
  })
})
