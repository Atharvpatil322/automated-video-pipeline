import { Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

import { ApiError } from '../api/client'
import { useArchetypes, useCreateJob, useHealth, usePlatforms, useProviders } from '../api/queries'
import { ArchetypePicker } from '../components/ArchetypePicker'
import { Card } from '../components/Card'
import { CollapsibleSection } from '../components/CollapsibleSection'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { OfflineBanner } from '../components/OfflineBanner'
import { PlatformPicker } from '../components/PlatformPicker'
import { ProviderKeysForm } from '../components/ProviderKeysForm'
import { useSettings } from '../state/settings'

const TOPIC_MAX = 500
const DIRECTION_MAX = 10_000

const SKIP_OPTIONS: {
  key: 'no_tts' | 'no_visuals' | 'no_video' | 'no_music' | 'no_critic'
  label: string
  hint: string
}[] = [
  { key: 'no_tts', label: 'Skip voiceover', hint: 'Fastest preview - no narration, no visuals or assembly either' },
  { key: 'no_visuals', label: 'Skip visuals', hint: 'Voiceover only, no images or video' },
  { key: 'no_video', label: 'Skip AI video clips', hint: 'Use still images instead of generated video' },
  { key: 'no_music', label: 'Skip background music', hint: '' },
  { key: 'no_critic', label: 'Skip final review', hint: 'No critic score at the end' },
]

export function Home() {
  const navigate = useNavigate()
  const { settings } = useSettings()
  const health = useHealth()
  const archetypes = useArchetypes()
  const platforms = usePlatforms()
  const providers = useProviders()
  const createJob = useCreateJob()

  const [topic, setTopic] = useState('')
  const [archetype, setArchetype] = useState('')
  const [platform, setPlatform] = useState('')
  const [direction, setDirection] = useState('')
  const [ttsProvider, setTtsProvider] = useState('')
  const [imageProvider, setImageProvider] = useState('')
  const [skip, setSkip] = useState<Record<string, boolean>>({})
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const defaultPlatform = platforms.data?.[0] ?? 'youtube'
  const ttsOptions = providers.data?.tts.filter((p) => p !== 'offline') ?? []
  const imageOptions = providers.data?.image.filter((p) => p !== 'offline') ?? []
  const defaultTts = ttsOptions[0] ?? 'elevenlabs'
  const defaultImage = imageOptions[0] ?? 'openai'

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setFieldErrors({})
    try {
      const job = await createJob.mutateAsync({
        topic,
        archetype: archetype || 'infographic',
        platform: platform || defaultPlatform,
        direction: direction || null,
        tts_provider: ttsProvider || defaultTts,
        image_provider: imageProvider || defaultImage,
        no_tts: Boolean(skip.no_tts),
        no_visuals: Boolean(skip.no_visuals),
        no_video: Boolean(skip.no_video),
        no_music: Boolean(skip.no_music),
        no_critic: Boolean(skip.no_critic),
        keys: settings.providerKeys,
      })
      navigate(`/jobs/${job.id}`)
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors({ topic: err.message })
      }
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5 p-4 sm:p-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <Sparkles className="h-6 w-6 text-primary" aria-hidden="true" />
          Make a video
        </h1>
        <p className="mt-1 text-muted-foreground">
          Give it a topic, pick a style, and we'll write, voice, shoot and edit it for you.
        </p>
      </div>

      {health.data?.offline && <OfflineBanner />}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Card className="space-y-4">
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="topic">What's it about?</Label>
              <span className="text-xs text-muted-foreground">
                {topic.length}/{TOPIC_MAX}
              </span>
            </div>
            <Textarea
              id="topic"
              required
              maxLength={TOPIC_MAX}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              rows={3}
              placeholder="e.g. the history of lighthouses"
            />
            {fieldErrors.topic && (
              <span role="alert" className="text-sm text-destructive">
                {fieldErrors.topic}
              </span>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label>Style</Label>
            {archetypes.isLoading ? (
              <LoadingState label="Loading styles…" />
            ) : archetypes.error ? (
              <ErrorState message="Could not load styles" />
            ) : (
              <ArchetypePicker
                archetypes={archetypes.data ?? []}
                value={archetype}
                onChange={setArchetype}
              />
            )}
          </div>

          <div className="flex flex-col gap-2">
            <Label>Platform</Label>
            <PlatformPicker
              platforms={platforms.data ?? []}
              value={platform || defaultPlatform}
              onChange={setPlatform}
            />
          </div>
        </Card>

        <CollapsibleSection
          title="Advanced options"
          description="Direction notes, which stages to skip, and your own API keys"
        >
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <Label htmlFor="direction">Direction (optional)</Label>
              <span className="text-xs text-muted-foreground">
                {direction.length}/{DIRECTION_MAX}
              </span>
            </div>
            <Textarea
              id="direction"
              maxLength={DIRECTION_MAX}
              value={direction}
              onChange={(e) => setDirection(e.target.value)}
              rows={3}
              placeholder="Anything specific you want the director to follow"
            />
          </div>

          <fieldset className="flex flex-col gap-3">
            <legend className="text-sm font-medium">Skip stages</legend>
            {SKIP_OPTIONS.map(({ key, label, hint }) => (
              <div key={key} className="flex items-start gap-2">
                <Checkbox
                  id={`skip-${key}`}
                  className="mt-0.5"
                  checked={Boolean(skip[key])}
                  onCheckedChange={(checked) =>
                    setSkip((prev) => ({ ...prev, [key]: checked === true }))
                  }
                />
                <Label htmlFor={`skip-${key}`} className="flex-col items-start gap-0.5 font-normal">
                  {label}
                  {hint && <span className="text-xs font-normal text-muted-foreground">{hint}</span>}
                </Label>
              </div>
            ))}
          </fieldset>

          <div className="space-y-3 border-t pt-4">
            <h3 className="text-sm font-medium">Providers</h3>
            {providers.isLoading ? (
              <LoadingState label="Loading providers…" />
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="flex flex-col gap-1.5">
                    <Label>Voiceover (TTS)</Label>
                    <Select value={ttsProvider || defaultTts} onValueChange={setTtsProvider}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ttsOptions.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <Label>Images</Label>
                    <Select value={imageProvider || defaultImage} onValueChange={setImageProvider}>
                      <SelectTrigger className="w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {imageOptions.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  LLM ({providers.data?.llm.filter((p) => p !== 'offline').join(', ')}), stock (
                  {providers.data?.stock.filter((p) => p !== 'offline').join(', ')}), video (
                  {providers.data?.video.filter((p) => p !== 'offline').join(', ')}) and music
                  (bundled royalty-free tracks) are chosen automatically from whichever keys you
                  provide below.
                </p>
                <ProviderKeysForm />
              </>
            )}
          </div>
        </CollapsibleSection>

        <Button type="submit" size="lg" disabled={createJob.isPending} className="w-full rounded-full sm:w-auto">
          {createJob.isPending ? 'Creating…' : 'Create video'}
        </Button>
      </form>
    </div>
  )
}
