import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('layout css', () => {
  it('keeps the debug dock in page flow instead of overlaying chat', () => {
    const dock = css.slice(css.indexOf('.debug-dock {'), css.indexOf('.debug-dock__bar'))
    expect(css).toContain('.app-frame')
    expect(dock).not.toMatch(/position:\s*fixed/)
    expect(css).not.toMatch(/padding-bottom:\s*56px/)
  })
})
