import { describe, expect, it } from 'vitest'
import { FOUNDATION_HINTS } from './foundationsHints'

describe('FOUNDATION_HINTS', () => {
  it('covers every foundations field with a hover description', () => {
    const keys = [
      'tenant.name',
      'tenant.slug',
      'operator.email',
      'proxmox.host',
      'proxmox.node',
      'proxmox.api_token_id',
      'proxmox.api_token_secret',
      'proxmox.ssh_key_fingerprint',
      'network.bridge',
      'network.address',
      'network.gateway',
      'network.ntp',
      'storage.pool',
      'domains.intended',
      'intent.mode.build',
      'intent.mode.adopt',
      'intent.mode.dns',
      'intent.url',
    ]
    expect(Object.keys(FOUNDATION_HINTS).sort()).toEqual([...keys].sort())
    for (const key of keys) {
      expect(FOUNDATION_HINTS[key as keyof typeof FOUNDATION_HINTS].length).toBeGreaterThan(20)
    }
  })
})
