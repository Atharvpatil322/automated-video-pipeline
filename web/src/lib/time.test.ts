import { describe, expect, it } from 'vitest'

import { parseServerTimestamp } from './time'

describe('parseServerTimestamp', () => {
  it('treats a timezone-less timestamp (datetime.utcnow() serialized as-is) as UTC', () => {
    expect(parseServerTimestamp('2026-01-01T12:00:00')).toBe(Date.parse('2026-01-01T12:00:00Z'))
  })

  it('leaves a timestamp that already carries a timezone untouched', () => {
    expect(parseServerTimestamp('2026-01-01T12:00:00+05:30')).toBe(
      Date.parse('2026-01-01T12:00:00+05:30'),
    )
  })

  it('leaves a Z-suffixed timestamp untouched', () => {
    expect(parseServerTimestamp('2026-01-01T12:00:00Z')).toBe(Date.parse('2026-01-01T12:00:00Z'))
  })
})
