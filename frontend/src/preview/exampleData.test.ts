import { describe, expect, it } from 'vitest'
import { emptyFoundations, foundationsYaml, summaryChecks } from './exampleData'

describe('exampleData', () => {
  it('marks incomplete foundations as failing checks', () => {
    const checks = summaryChecks(emptyFoundations())
    expect(checks.filter((item) => item.status === 'fail').map((item) => item.id)).toEqual([
      'proxmox',
      'network',
      'provider',
      'tenant',
    ])
  })

  it('exports references, not secret values', () => {
    const yaml = foundationsYaml({
      ...emptyFoundations(),
      tenant: { name: 'Riley Lab', slug: 'riley-lab' },
      proxmox: { host: '192.0.2.10', node: 'pve', tokenId: 'root@pam!shed', tokenSet: true },
    })
    expect(yaml).toContain('slug: riley-lab')
    expect(yaml).toContain('api_token_ref: local://proxmox/api_token')
    expect(yaml).not.toContain('root@pam!shed')
  })
})
