import { useCallback, useState } from 'react'

// sessionStorage only, never localStorage - BYOK provider keys must not
// survive past the browser tab's lifetime. Every read/write is wrapped:
// private browsing, blocked site data and SSR-less previews can all throw
// or return nothing.
export function useSessionStorage<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(key)
      return raw ? (JSON.parse(raw) as T) : initial
    } catch {
      return initial
    }
  })

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? (next as (prev: T) => T)(prev) : next
        try {
          sessionStorage.setItem(key, JSON.stringify(resolved))
        } catch {
          // ignore - storage may be unavailable (private mode, blocked, etc.)
        }
        return resolved
      })
    },
    [key],
  )

  const clear = useCallback(() => {
    try {
      sessionStorage.removeItem(key)
    } catch {
      // ignore
    }
    setValue(initial)
  }, [key, initial])

  return [value, set, clear] as const
}
