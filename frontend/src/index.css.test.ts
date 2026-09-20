import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8')

describe('layout css', () => {
  it('keeps the debug dock in page flow instead of overlaying chat', () => {
    const dock = css.slice(css.indexOf('.debug-dock {'), css.indexOf('.debug-dock__bar'))
    const shell = css.slice(css.indexOf('.app-shell {'), css.indexOf('.app-header {'))
    expect(css).toContain('.app-frame')
    expect(dock).toMatch(/position:\s*static/)
    expect(dock).toMatch(/grid-column:\s*1\s*\/\s*-1/)
    expect(dock).not.toMatch(/position:\s*fixed/)
    expect(shell).toMatch(/grid-template-rows:\s*auto\s+minmax\(0,\s*1fr\)\s+auto/)
    expect(css).not.toMatch(/padding-bottom:\s*56px/)
  })
})
