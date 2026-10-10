import type { ReactNode } from 'react'
import { useCallback } from 'react'

import { useSessionStorage } from '../hooks/useSessionStorage'
import { DEFAULT_SETTINGS, SettingsContext, type SettingsState } from './settings'

const STORAGE_KEY = 'video-pipeline:settings'

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings, clear] = useSessionStorage<SettingsState>(
    STORAGE_KEY,
    DEFAULT_SETTINGS,
  )

  const clearKeys = useCallback(() => {
    setSettings((prev) => ({ ...prev, providerKeys: {} }))
  }, [setSettings])

  void clear // full reset not currently exposed in the UI; keep the lint quiet

  return (
    <SettingsContext.Provider value={{ settings, setSettings, clearKeys }}>
      {children}
    </SettingsContext.Provider>
  )
}
