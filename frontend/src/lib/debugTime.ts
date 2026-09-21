/** UTC / UTC±offset for the viewing system's local timezone. */
export function formatUtcOffsetLabel(date: Date): string {
  const offsetMinutes = -date.getTimezoneOffset()
  if (offsetMinutes === 0) return 'UTC'
  const sign = offsetMinutes > 0 ? '+' : '-'
  const abs = Math.abs(offsetMinutes)
  const hours = Math.floor(abs / 60)
  const minutes = abs % 60
  if (minutes === 0) return `UTC${sign}${hours}`
  return `UTC${sign}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

/** Format a debug-event `at` value as the viewing system's local clock plus timezone. */
export function formatDebugTimestamp(at: string): string {
  if (!at) return 'unknown time'
  const date = new Date(at)
  if (Number.isNaN(date.getTime())) return at
  const pad = (value: number) => String(value).padStart(2, '0')
  const clock = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  return `${clock} ${formatUtcOffsetLabel(date)}`
}

/** One dock/console line: clock first, then source · event, then the message. */
export function formatDebugLine(item: {
  stamp?: string
  at?: string
  source: string
  event: string
  message: string
}): string {
  const stamp = item.stamp?.trim() || formatDebugTimestamp(item.at ?? '')
  return `${stamp}  ${item.source} · ${item.event}  ${item.message}`
}
