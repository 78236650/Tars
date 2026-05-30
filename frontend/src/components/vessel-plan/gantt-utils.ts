export function parseTime(iso: string): number {
  return new Date(iso).getTime()
}

export function timeToX(
  iso: string,
  startMs: number,
  endMs: number,
  width: number,
  padding = 8,
): number {
  const t = parseTime(iso)
  const span = endMs - startMs || 1
  return padding + ((t - startMs) / span) * (width - padding * 2)
}

export function durationToWidth(
  startIso: string,
  endIso: string,
  startMs: number,
  endMs: number,
  width: number,
  padding = 8,
): number {
  const inner = width - padding * 2
  const span = endMs - startMs || 1
  const dur = parseTime(endIso) - parseTime(startIso)
  return Math.max(4, (dur / span) * inner)
}

export function formatHourLabel(iso: string, locale: string): string {
  return new Date(iso).toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
