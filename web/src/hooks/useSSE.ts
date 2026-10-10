import { useEffect, useRef, useState } from 'react'

import type { SettingsState } from '../state/settings'

export interface SSEEvent {
  event: string
  data: unknown
}

type ConnectionStatus = 'connecting' | 'open' | 'closed'

const TERMINAL_EVENTS = new Set(['job.completed', 'job.failed', 'job.cancelled'])
const RECONNECT_BASE_MS = 500
const RECONNECT_MAX_MS = 8_000

/** SSE framing, by hand, because EventSource cannot set an Authorization
 * header and the API requires one whenever API_TOKEN is set (see
 * app/server/routes/events.py, which uses sse_starlette - standard
 * `event: ...\ndata: ...\n\n` framing over a chunked response).
 *
 * The parser buffers raw text across chunk boundaries (a chunk can split
 * a line, or even split "event: stage.t" / "ts\n"), splits on blank lines
 * to find whole events, and within each event block reads one or more
 * `data:` lines (multi-line data fields are joined with "\n", per the SSE
 * spec) plus one `event:` line. A line starting with `:` is a comment -
 * the server sends `: keepalive` on its 15s idle timeout - and is
 * ignored rather than treated as a field.
 */
function parseSSEBlock(block: string): SSEEvent | null {
  let eventType = 'message'
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line === '' || line.startsWith(':')) continue
    if (line.startsWith('event:')) {
      eventType = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }
  if (dataLines.length === 0) return null
  const raw = dataLines.join('\n')
  try {
    return { event: eventType, data: JSON.parse(raw) }
  } catch {
    return { event: eventType, data: raw }
  }
}

export async function* readSSEStream(
  response: Response,
  signal: AbortSignal,
): AsyncGenerator<SSEEvent> {
  const body = response.body
  if (!body) return
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (!signal.aborted) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      // SSE events are separated by a blank line; \r\n and \n both occur
      // depending on the server/proxy, so normalize before splitting.
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary !== -1) {
        const block = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const parsed = parseSSEBlock(block)
        if (parsed) yield parsed
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.cancel().catch(() => {})
  }
}

export function useSSE(
  jobId: string | undefined,
  settings: SettingsState,
  onEvent: (event: SSEEvent) => void,
) {
  const [status, setStatus] = useState<ConnectionStatus>('connecting')
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!jobId) return
    let stopped = false
    let attempt = 0
    const controller = new AbortController()

    async function connectOnce() {
      setStatus('connecting')
      try {
        const response = await fetch(
          `${settings.apiBaseUrl}/api/v1/jobs/${jobId}/events`,
          {
            headers: settings.apiToken ? { Authorization: `Bearer ${settings.apiToken}` } : {},
            signal: controller.signal,
          },
        )
        if (!response.ok) throw new Error(`events stream failed: ${response.status}`)
        setStatus('open')
        attempt = 0
        for await (const sseEvent of readSSEStream(response, controller.signal)) {
          onEventRef.current(sseEvent)
          if (TERMINAL_EVENTS.has(sseEvent.event)) {
            stopped = true
            setStatus('closed')
            return
          }
        }
      } catch {
        // network error, abort, or a non-2xx - reconnect below unless
        // we've been told to stop (unmount, or a terminal event already
        // closed the loop on purpose).
      }
      if (stopped || controller.signal.aborted) return
      setStatus('connecting')
      const delay = Math.min(RECONNECT_BASE_MS * 2 ** attempt, RECONNECT_MAX_MS)
      attempt += 1
      setTimeout(() => {
        if (!controller.signal.aborted) void connectOnce()
      }, delay)
    }

    void connectOnce()

    return () => {
      stopped = true
      controller.abort()
    }
  }, [jobId, settings.apiBaseUrl, settings.apiToken])

  return status
}
