import { describe, expect, it } from 'vitest'
import { formatDebugTimestamp, formatUtcOffsetLabel } from './debugTime'

describe('formatDebugTimestamp', () => {
  it('formats a local clock with a UTC or UTC-offset timezone label', () => {
    const at = '2026-09-20T14:05:06.123Z'
    const formatted = formatDebugTimestamp(at)
    const date = new Date(at)
    const pad = (value: number) => String(value).padStart(2, '0')
    const clock = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    expect(formatted).toBe(`${clock} ${formatUtcOffsetLabel(date)}`)
    expect(formatted).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC([+-]\d{1,2}(:\d{2})?)?$/)
    expect(formatted).not.toMatch(/^\d{4}-\d{2}-\d{2}T/)
    expect(formatted.endsWith('Z')).toBe(false)
  })

  it('labels the zero offset as UTC', () => {
    const date = new Date('2026-09-20T14:05:06Z')
    const original = Date.prototype.getTimezoneOffset
    Date.prototype.getTimezoneOffset = () => 0
    try {
      expect(formatUtcOffsetLabel(date)).toBe('UTC')
      expect(formatDebugTimestamp('2026-09-20T14:05:06Z')).toContain(' UTC')
    } finally {
      Date.prototype.getTimezoneOffset = original
    }
  })

  it('labels a positive offset without minutes as UTC+10', () => {
    const date = new Date('2026-09-20T14:05:06Z')
    const original = Date.prototype.getTimezoneOffset
    Date.prototype.getTimezoneOffset = () => -600
    try {
      expect(formatUtcOffsetLabel(date)).toBe('UTC+10')
    } finally {
      Date.prototype.getTimezoneOffset = original
    }
  })

  it('keeps an unparseable value so the dock still shows a stamp', () => {
    expect(formatDebugTimestamp('not-a-time')).toBe('not-a-time')
    expect(formatDebugTimestamp('')).toBe('unknown time')
  })
})
