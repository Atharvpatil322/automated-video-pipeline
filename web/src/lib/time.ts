const HAS_TIMEZONE = /(Z|[+-]\d{2}:?\d{2})$/

/** The API serializes `datetime.utcnow()` values (naive, but UTC) as plain
 * ISO strings with no "Z"/offset - Pydantic has no way to know they're UTC
 * since the datetime objects themselves carry no tzinfo. `new Date(iso)`
 * then reads them as local time, which is wrong by exactly the browser's
 * UTC offset. Treat any timestamp with no timezone designator as UTC.
 */
export function parseServerTimestamp(iso: string): number {
  const normalized = HAS_TIMEZONE.test(iso) ? iso : `${iso}Z`
  return new Date(normalized).getTime()
}

export function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}
