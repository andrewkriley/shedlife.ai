import { describe, expect, it } from 'vitest'
import { isPreviewLocation } from './previewMode'

describe('isPreviewLocation', () => {
  it('matches the preview hash', () => {
    expect(isPreviewLocation({ hash: '#/preview', search: '' })).toBe(true)
  })

  it('matches ?preview=1', () => {
    expect(isPreviewLocation({ hash: '', search: '?preview=1' })).toBe(true)
  })

  it('ignores the live product', () => {
    expect(isPreviewLocation({ hash: '', search: '' })).toBe(false)
    expect(isPreviewLocation({ hash: '#/settings', search: '' })).toBe(false)
  })
})
