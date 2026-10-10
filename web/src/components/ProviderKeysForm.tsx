import { useSettings } from '../state/settings'

// Every vendor key the factory (app/providers/factory.py) ever reads from
// a job's `keys` map. Not all are user-selectable providers - groq backs
// both the LLM and (for openai TTS / stock verification) word alignment
// and vision, so it's listed once here regardless of which stage uses it.
const KNOWN_KEYS: { id: string; label: string }[] = [
  { id: 'groq', label: 'Groq (LLM, word alignment, stock verification)' },
  { id: 'elevenlabs', label: 'ElevenLabs (voiceover)' },
  { id: 'openai', label: 'OpenAI (voiceover, images)' },
  { id: 'gemini', label: 'Gemini (images)' },
  { id: 'pexels', label: 'Pexels (stock)' },
  { id: 'pixabay', label: 'Pixabay (stock)' },
  { id: 'fal', label: 'fal.ai (video)' },
]

export function ProviderKeysForm() {
  const { settings, setSettings, clearKeys } = useSettings()

  function setKey(id: string, value: string) {
    setSettings((prev) => ({ ...prev, providerKeys: { ...prev.providerKeys, [id]: value } }))
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500 dark:text-slate-400">
        Keys are kept in this browser tab's sessionStorage only - never localStorage, never sent
        anywhere except as part of creating a job. They're cleared when the tab closes, or with
        the button below.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {KNOWN_KEYS.map(({ id, label }) => (
          <label key={id} className="flex flex-col gap-1 text-sm">
            <span>{label}</span>
            <input
              type="password"
              autoComplete="off"
              value={settings.providerKeys[id] ?? ''}
              onChange={(e) => setKey(id, e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
            />
          </label>
        ))}
      </div>
      <button
        type="button"
        onClick={clearKeys}
        className="rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"
      >
        Clear keys
      </button>
    </div>
  )
}
