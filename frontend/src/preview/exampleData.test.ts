import { describe, expect, it } from 'vitest'
import {
  emptyJourney,
  itemsForPhase,
  journeyYaml,
  phaseProgress,
  prereqReady,
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

  it('hides secret row values', () => {
    const item = itemsForPhase('prereq').find((entry) => entry.id === 'openrouter')
    expect(item).toBeDefined()
    if (!item) return
    expect(rowDetail(item, { values: { apiKey: 'sk-or-preview' }, done: false })).toBe('Saved')
    expect(rowDetail(item, { values: { apiKey: '' }, done: false })).toBe('Not set')
  })
})
