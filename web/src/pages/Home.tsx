import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client'
import { useArchetypes, useCreateJob, useHealth, usePlatforms, useProviders } from '../api/queries'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { OfflineBanner } from '../components/OfflineBanner'
import { ProviderKeysForm } from '../components/ProviderKeysForm'
import { useSettings } from '../state/settings'

const TOPIC_MAX = 500
const DIRECTION_MAX = 10_000
const LET_DIRECTOR_CHOOSE = ''

export function Home() {
  const navigate = useNavigate()
  const { settings } = useSettings()
  const health = useHealth()
  const archetypes = useArchetypes()
  const platforms = usePlatforms()
  const providers = useProviders()
  const createJob = useCreateJob()

  const [topic, setTopic] = useState('')
  const [archetype, setArchetype] = useState(LET_DIRECTOR_CHOOSE)
  const [platform, setPlatform] = useState('')
  const [direction, setDirection] = useState('')
  const [ttsProvider, setTtsProvider] = useState('')
  const [imageProvider, setImageProvider] = useState('')
  const [noTts, setNoTts] = useState(false)
  const [noVisuals, setNoVisuals] = useState(false)
  const [noVideo, setNoVideo] = useState(false)
  const [noMusic, setNoMusic] = useState(false)
  const [noCritic, setNoCritic] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const defaultPlatform = platforms.data?.[0] ?? 'youtube'
  const defaultTts = providers.data?.tts.filter((p) => p !== 'offline')[0] ?? 'elevenlabs'
  const defaultImage = providers.data?.image.filter((p) => p !== 'offline')[0] ?? 'openai'

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
        no_tts: noTts,
        no_visuals: noVisuals,
        no_video: noVideo,
        no_music: noMusic,
        no_critic: noCritic,
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
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <h1 className="text-2xl font-bold">New job</h1>
      {health.data?.offline && <OfflineBanner />}

      <form onSubmit={handleSubmit} className="space-y-4">
        <label className="flex flex-col gap-1">
          <span className="flex justify-between text-sm font-medium">
            <span>Topic</span>
            <span className="text-slate-400">
              {topic.length}/{TOPIC_MAX}
            </span>
          </span>
          <textarea
            required
            maxLength={TOPIC_MAX}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            rows={3}
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          />
          {fieldErrors.topic && (
            <span role="alert" className="text-sm text-red-600 dark:text-red-400">
              {fieldErrors.topic}
            </span>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Archetype</span>
          {archetypes.isLoading ? (
            <LoadingState label="Loading archetypes…" />
          ) : archetypes.error ? (
            <ErrorState message="Could not load archetypes" />
          ) : (
            <select
              value={archetype}
              onChange={(e) => setArchetype(e.target.value)}
              className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
            >
              <option value={LET_DIRECTOR_CHOOSE}>Let the director choose</option>
              {archetypes.data?.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Platform</span>
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          >
            {platforms.data?.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1">
          <span className="flex justify-between text-sm font-medium">
            <span>Direction (optional)</span>
            <span className="text-slate-400">
              {direction.length}/{DIRECTION_MAX}
            </span>
          </span>
          <textarea
            maxLength={DIRECTION_MAX}
            value={direction}
            onChange={(e) => setDirection(e.target.value)}
            rows={3}
            className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
          />
        </label>

        <fieldset className="flex flex-wrap gap-4">
          <legend className="text-sm font-medium">Options</legend>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={noTts} onChange={(e) => setNoTts(e.target.checked)} />
            Dry run (skip TTS)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={noVisuals}
              onChange={(e) => setNoVisuals(e.target.checked)}
            />
            No visuals
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={noVideo}
              onChange={(e) => setNoVideo(e.target.checked)}
            />
            No video
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={noMusic}
              onChange={(e) => setNoMusic(e.target.checked)}
            />
            No music
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={noCritic}
              onChange={(e) => setNoCritic(e.target.checked)}
            />
            No critic
          </label>
        </fieldset>

        <section className="space-y-3 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
          <h2 className="text-sm font-semibold">Providers</h2>
          {providers.isLoading ? (
            <LoadingState label="Loading providers…" />
          ) : (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                  <span>Voiceover (TTS)</span>
                  <select
                    value={ttsProvider}
                    onChange={(e) => setTtsProvider(e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
                  >
                    {providers.data?.tts
                      .filter((p) => p !== 'offline')
                      .map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span>Images</span>
                  <select
                    value={imageProvider}
                    onChange={(e) => setImageProvider(e.target.value)}
                    className="rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
                  >
                    {providers.data?.image
                      .filter((p) => p !== 'offline')
                      .map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                  </select>
                </label>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                LLM ({providers.data?.llm.filter((p) => p !== 'offline').join(', ')}), stock (
                {providers.data?.stock.filter((p) => p !== 'offline').join(', ')}), video (
                {providers.data?.video.filter((p) => p !== 'offline').join(', ')}) and music
                (bundled royalty-free tracks) are chosen automatically from whichever keys you
                provide below - there's nothing to select for them.
              </p>
              <ProviderKeysForm />
            </>
          )}
        </section>

        <button
          type="submit"
          disabled={createJob.isPending}
          className="rounded-md bg-brand px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {createJob.isPending ? 'Creating…' : 'Create job'}
        </button>
      </form>
    </div>
  )
}
