import { describe, expect, it } from 'vitest'
import {
  emptyJourney,
  itemsForPhase,
  joinTitles,
  journeyYaml,
  phaseProgress,
  prereqReady,
  prereqSummary,
  rowDetail,
} from './exampleData'

describe('exampleData', () => {
  it('counts an empty Pre-req phase as 0 of 8', () => {
    expect(itemsForPhase('prereq')).toHaveLength(8)
    expect(phaseProgress('prereq', emptyJourney())).toEqual({ done: 0, total: 8 })
    expect(prereqReady(emptyJourney())).toBe(false)
  })

  it('exports references, not secret values', () => {
    const state = emptyJourney()
    state['proxmox-ip'].values.host = '192.0.2.10'
    state['proxmox-token-secret'].values.tokenSecret = 'super-secret'
    state['openrouter'].values.apiKey = 'sk-or-preview'
    state['domain'].values.domain = 'lab.example'
    const yaml = journeyYaml(state)
    expect(yaml).toContain('proxmox_host: 192.0.2.10')
    expect(yaml).toContain('openrouter_ref: local://providers/openrouter/api_key')
    expect(yaml).not.toContain('super-secret')
    expect(yaml).not.toContain('sk-or-preview')
  })

  it('summarizes Pre-req without secret values', () => {
    const state = emptyJourney()
    state['proxmox-ip'].values.host = '192.0.2.10'
    state['domain'].values.domain = 'lab.example'
    state['openrouter'].values.apiKey = 'sk-or-preview'
    expect(prereqSummary(state)).toBe(
      'Proxmox is 192.0.2.10. Services will aim at lab.example. Tokens, keys, and the SSH trust are saved locally.',
    )
    expect(prereqSummary(state)).not.toContain('sk-or-preview')
    expect(joinTitles('deploy')).toContain('GitLab')
    expect(joinTitles('deploy')).toContain('StepCA')
  })

  it('hides secret row values', () => {
    const item = itemsForPhase('prereq').find((entry) => entry.id === 'openrouter')
    expect(item).toBeDefined()
    if (!item) return
    expect(rowDetail(item, { values: { apiKey: 'sk-or-preview' }, done: false })).toBe('Saved')
    expect(rowDetail(item, { values: { apiKey: '' }, done: false })).toBe('Not set')
  })
})
