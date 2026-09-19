import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { IssuesPanel } from './IssuesPanel'
import * as api from '../lib/api'

describe('IssuesPanel', () => {
  it('lists issues and files a new one', async () => {
    vi.spyOn(api, 'getIssues')
      .mockResolvedValueOnce([
        {
          id: '1',
          classification: 'environment',
          summary: 'probe outbound_https crashed',
          detail: 'socket closed',
          source: 'automatic',
          filed_externally: null,
          created_at: '2026-09-20T00:00:00Z',
        },
      ])
      .mockResolvedValueOnce([
        {
          id: '1',
          classification: 'environment',
          summary: 'probe outbound_https crashed',
          detail: 'socket closed',
          source: 'automatic',
          filed_externally: null,
          created_at: '2026-09-20T00:00:00Z',
        },
        {
          id: '2',
          classification: 'product-bug',
          summary: 'UI 500',
          detail: 'boom',
          source: 'operator',
          filed_externally: null,
          created_at: '2026-09-20T00:01:00Z',
        },
      ])
    const fileIssue = vi.spyOn(api, 'fileIssue').mockResolvedValue({
      id: '2',
      classification: 'product-bug',
      summary: 'UI 500',
      detail: 'boom',
      source: 'operator',
      filed_externally: null,
      created_at: '2026-09-20T00:01:00Z',
    })

    const user = userEvent.setup()
    render(<IssuesPanel />)

    expect(await screen.findByText(/probe outbound_https crashed/)).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Open issues' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'File an issue' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Summary'), 'UI 500')
    await user.type(screen.getByLabelText('Detail'), 'boom')
    await user.click(screen.getByRole('button', { name: 'File issue' }))

    expect(fileIssue).toHaveBeenCalledWith({ summary: 'UI 500', detail: 'boom' })
    expect(await screen.findByText(/UI 500/)).toBeInTheDocument()
  })
})
