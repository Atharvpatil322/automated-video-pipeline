import { renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_SETTINGS } from '../state/settings'
import { readSSEStream, useSSE, type SSEEvent } from './useSSE'

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  let i = 0
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) {
        controller.enqueue(encoder.encode(chunks[i]))
        i += 1
      } else {
        controller.close()
      }
    },
  })
}

function responseOf(chunks: string[]): Response {
  return new Response(streamOf(chunks), { status: 200 })
}

describe('readSSEStream (SSE framing parser)', () => {
  async function collect(chunks: string[]): Promise<SSEEvent[]> {
    const events: SSEEvent[] = []
    for await (const event of readSSEStream(responseOf(chunks), new AbortController().signal)) {
      events.push(event)
    }
    return events
  }

  it('parses a whole event delivered in one chunk', async () => {
    const events = await collect(['event: job.snapshot\ndata: {"status":"running"}\n\n'])
    expect(events).toEqual([{ event: 'job.snapshot', data: { status: 'running' } }])
  })

  it('joins multi-line data fields with newlines, per the SSE spec', async () => {
    const events = await collect(['event: progress.research\ndata: line one\ndata: line two\n\n'])
    expect(events).toEqual([{ event: 'progress.research', data: 'line one\nline two' }])
  })

  it('ignores comment lines used as keepalives', async () => {
    const events = await collect([': keepalive\n\nevent: stage.tts\ndata: {"status":"running"}\n\n'])
    expect(events).toEqual([{ event: 'stage.tts', data: { status: 'running' } }])
  })

  it('reassembles an event split across chunk boundaries, mid-field and mid-line', async () => {
    const events = await collect([
      'event: stage.',
      'tts\ndata: {"stat',
      'us":"completed"}\n',
      '\nevent: job.completed\ndata: {}\n\n',
    ])
    expect(events).toEqual([
      { event: 'stage.tts', data: { status: 'completed' } },
      { event: 'job.completed', data: {} },
    ])
  })

  it('falls back to the raw string when data is not JSON', async () => {
    const events = await collect(['event: message\ndata: not json\n\n'])
    expect(events).toEqual([{ event: 'message', data: 'not json' }])
  })
})

describe('useSSE', () => {
  const settings = DEFAULT_SETTINGS

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('delivers job.snapshot first, then stage events, in order', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        responseOf([
          'event: job.snapshot\ndata: {"id":"job-1"}\n\n',
          'event: stage.research\ndata: {"status":"running"}\n\n',
        ]),
      ),
    )
    const received: SSEEvent[] = []
    renderHook(() => useSSE('job-1', settings, (e) => received.push(e)))

    await waitFor(() => expect(received).toHaveLength(2))
    expect(received[0]).toEqual({ event: 'job.snapshot', data: { id: 'job-1' } })
    expect(received[1]).toEqual({ event: 'stage.research', data: { status: 'running' } })
  })

  it('stops after a terminal event without reconnecting', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(responseOf(['event: job.completed\ndata: {"status":"completed"}\n\n']))
    vi.stubGlobal('fetch', fetchMock)

    const received: SSEEvent[] = []
    const { result } = renderHook(() => useSSE('job-1', settings, (e) => received.push(e)))

    await waitFor(() => expect(result.current).toBe('closed'))
    expect(received).toEqual([{ event: 'job.completed', data: { status: 'completed' } }])

    // give any (incorrect) reconnect attempt a real chance to happen
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('reconnects with backoff after a dropped connection, and resyncs via a fresh snapshot', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('network drop'))
      .mockResolvedValueOnce(responseOf(['event: job.snapshot\ndata: {"id":"job-1"}\n\n']))
    vi.stubGlobal('fetch', fetchMock)

    const received: SSEEvent[] = []
    renderHook(() => useSSE('job-1', settings, (e) => received.push(e)))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    // first backoff delay is 500ms - wait past it on real timers rather
    // than faking them (fake timers don't play well with waitFor's own
    // polling, which also relies on timers).
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2), { timeout: 2000 })
    await waitFor(() => expect(received).toHaveLength(1))
    expect(received[0]).toEqual({ event: 'job.snapshot', data: { id: 'job-1' } })
  })
})
