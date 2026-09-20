/** Format a debug-event `at` value as the viewing system's local clock. */
export function formatDebugTimestamp(at: string): string {
  const date = new Date(at)
  if (Number.isNaN(date.getTime())) return at
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
