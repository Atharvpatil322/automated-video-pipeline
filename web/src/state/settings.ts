import { createContext, useContext } from 'react'

export interface SettingsState {
  apiBaseUrl: string
  apiToken: string
  providerKeys: Record<string, string>
}

export const DEFAULT_SETTINGS: SettingsState = {
  apiBaseUrl: '',
  apiToken: '',
  providerKeys: {},
}

export interface SettingsContextValue {
  settings: SettingsState
  setSettings: (next: SettingsState | ((prev: SettingsState) => SettingsState)) => void
  clearKeys: () => void
}

export const SettingsContext = createContext<SettingsContextValue | null>(null)

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) {
    throw new Error('useSettings must be used within SettingsProvider')
  }
  return ctx
}
