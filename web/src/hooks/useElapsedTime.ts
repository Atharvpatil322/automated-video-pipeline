import { useEffect, useState } from 'react'

import { formatDuration, parseServerTimestamp } from '../lib/time'

/** Ticks once a second while `running`, from `startedAt` to `endedAt` (or
 * now). Returns a formatted mm:ss / h:mm:ss string.
 */
export function useElapsedTime(
  startedAt: string | null | undefined,
  endedAt: string | null | undefined,
  running: boolean,
): string | null {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!running) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [running])

  if (!startedAt) return null
  const start = parseServerTimestamp(startedAt)
  const end = endedAt ? parseServerTimestamp(endedAt) : now
  return formatDuration((end - start) / 1000)
}
