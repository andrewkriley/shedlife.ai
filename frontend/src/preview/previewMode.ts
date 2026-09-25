export const PREVIEW_HASH = '#/preview'

export function isPreviewLocation(
  location: Pick<Location, 'hash' | 'search'> = window.location,
): boolean {
  const hash = location.hash.split('?')[0]
  if (hash === PREVIEW_HASH) return true
  return new URLSearchParams(location.search).get('preview') === '1'
}
