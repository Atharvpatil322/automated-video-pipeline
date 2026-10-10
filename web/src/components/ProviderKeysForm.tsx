import { KeyRound, ShieldCheck, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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
      <p className="flex items-start gap-2 text-sm text-muted-foreground">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-success)]" aria-hidden="true" />
        <span>
          Kept in this browser tab's sessionStorage only — never localStorage, never sent anywhere
          except as part of creating a job. Cleared when the tab closes, or with the button below.
        </span>
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {KNOWN_KEYS.map(({ id, label }) => (
          <div key={id} className="flex flex-col gap-1.5">
            <Label htmlFor={`key-${id}`} className="text-sm font-normal">
              {label}
            </Label>
            <div className="relative">
              <KeyRound
                className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id={`key-${id}`}
                type="password"
                autoComplete="off"
                value={settings.providerKeys[id] ?? ''}
                onChange={(e) => setKey(id, e.target.value)}
                className="h-9 pl-8"
              />
            </div>
          </div>
        ))}
      </div>
      <Button type="button" variant="outline" size="sm" className="rounded-full" onClick={clearKeys}>
        <Trash2 aria-hidden="true" />
        Clear keys
      </Button>
    </div>
  )
}
