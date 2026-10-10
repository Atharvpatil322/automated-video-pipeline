import { Clock, Trash2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'

import { useCancelJob, useDeleteJob, useJob, useVisuals } from '../api/queries'
import type { JobDocument, RevisionHistoryEntry, StageName, StageRecord } from '../api/types'
import { Card } from '../components/Card'
import { CostPanel } from '../components/CostPanel'
import { CriticReview } from '../components/CriticReview'
import { ErrorState } from '../components/ErrorState'
import { LoadingState } from '../components/LoadingState'
import { PipelineVisualization } from '../components/PipelineVisualization'
import { ResearchSummary } from '../components/ResearchSummary'
import { RevisionHistory } from '../components/RevisionHistory'
import { SceneGallery } from '../components/SceneGallery'
import { SceneTable } from '../components/SceneTable'
import { StatusBadge } from '../components/StatusBadge'
import { VideoPlayer } from '../components/VideoPlayer'
import { useElapsedTime } from '../hooks/useElapsedTime'
import { useSSE } from '../hooks/useSSE'
import { useSettings } from '../state/settings'

const TERMINAL = new Set(['completed', 'failed', 'cancelled'])

function applyStageEvent(job: JobDocument, stage: StageName, payload: Record<string, unknown>): JobDocument {
  const record: StageRecord = {
    ...job.stages[stage],
    status: (payload.status as StageRecord['status']) ?? job.stages[stage].status,
  }
  if ('detail' in payload) record.detail = payload.detail as StageRecord['detail']
  if ('reason' in payload) record.reason = payload.reason as string
  if ('error' in payload) record.error = payload.error as string
  return {
    ...job,
    // The worker flips the job to "running" before the first stage starts
    // (app/server/pipeline_runner.py), but that transition isn't its own
    // SSE event - only stage.* events are published while a job runs. A
    // client that connects while the job is still "queued" (the common
    // case, right after creation) never hears about it otherwise.
    status: job.status === 'queued' ? 'running' : job.status,
    stages: { ...job.stages, [stage]: record },
  }
}

export function Job() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const { settings } = useSettings()
  const jobQuery = useJob(jobId)
  const cancelJob = useCancelJob()
  const deleteJob = useDeleteJob()

  const [live, setLive] = useState<JobDocument | null>(null)
  const [confirmingCancel, setConfirmingCancel] = useState(false)

  // Reset the live SSE snapshot when navigating to a different job, during
  // render rather than in an effect - this is React's documented pattern
  // for resetting state in response to a prop change (it bails out before
  // committing, so it never causes a visible extra render).
  const [liveForJobId, setLiveForJobId] = useState(jobId)
  if (jobId !== liveForJobId) {
    setLiveForJobId(jobId)
    setLive(null)
  }

  const job = live ?? jobQuery.data ?? null

  // run_dir and started_at are set on Mongo directly by the worker
  // (app/server/pipeline_runner.py's initial `_set(...)`, and
  // on_run_dir in app/server/callbacks.py) without a matching SSE event -
  // only stage/cost/review changes are published to the job's Redis
  // channel. A client whose SSE connection opens before the worker picks
  // up the job (the usual case, right after creating one) never learns
  // either field from `live` alone, which breaks the elapsed-time clock
  // and scene/video asset URLs (both need one of these). A short REST
  // poll backfills them once they exist, without needing a backend change.
  useEffect(() => {
    if (!live || TERMINAL.has(live.status)) return
    if (live.run_dir && live.started_at) return
    let cancelled = false
    const interval = setInterval(() => {
      void jobQuery.refetch().then((result) => {
        if (cancelled || !result.data) return
        setLive((prev) =>
          prev
            ? {
                ...prev,
                run_dir: prev.run_dir ?? result.data!.run_dir,
                started_at: prev.started_at ?? result.data!.started_at,
              }
            : prev,
        )
      })
    }, 2000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [live?.run_dir, live?.started_at, live?.status, jobId])

  useSSE(jobId, settings, (event) => {
    if (event.event === 'job.snapshot') {
      setLive(event.data as JobDocument)
      return
    }
    if (event.event.startsWith('stage.')) {
      const stage = event.event.slice('stage.'.length) as StageName
      setLive((prev) => (prev ? applyStageEvent(prev, stage, event.data as Record<string, unknown>) : prev))
      return
    }
    if (event.event === 'cost.estimate') {
      setLive((prev) => (prev ? { ...prev, cost_estimate: event.data as JobDocument['cost_estimate'] } : prev))
      return
    }
    if (event.event.startsWith('progress.')) {
      const data = event.data as Record<string, unknown>
      setLive((prev) => {
        if (!prev) return prev
        const next = { ...prev }
        if (data.review) next.review = data.review as JobDocument['review']
        if (data.revision) {
          next.revision_history = [
            ...prev.revision_history,
            data.revision as RevisionHistoryEntry,
          ]
        }
        return next
      })
      return
    }
    if (event.event === 'job.completed' || event.event === 'job.failed' || event.event === 'job.cancelled') {
      void jobQuery.refetch()
    }
  })

  const visuals = useVisuals(jobId, job?.stages.visuals.status === 'completed')

  const elapsed = useElapsedTime(job?.started_at, job?.finished_at, Boolean(job && !TERMINAL.has(job.status)))

  if (jobQuery.isLoading && !job) return <LoadingState label="Loading job…" />
  if (jobQuery.error && !job) return <ErrorState message="Could not load this job." />
  if (!job) return <ErrorState message="Job not found." />

  async function handleCancel() {
    if (!jobId) return
    await cancelJob.mutateAsync(jobId)
    setConfirmingCancel(false)
  }

  async function handleDelete() {
    if (!jobId) return
    await deleteJob.mutateAsync(jobId)
    navigate('/gallery')
  }

  const isTerminal = TERMINAL.has(job.status)

  return (
    <div className="mx-auto max-w-4xl space-y-5 p-4 sm:p-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h1 className="text-xl font-bold">{job.options.topic}</h1>
          <StatusBadge status={job.status} />
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          {elapsed && (
            <span className="flex items-center gap-1">
              <Clock className="h-4 w-4" aria-hidden="true" />
              {elapsed}
            </span>
          )}
          {!isTerminal && !confirmingCancel && (
            <Button variant="outline" size="sm" className="rounded-full" onClick={() => setConfirmingCancel(true)}>
              <XCircle aria-hidden="true" />
              Cancel
            </Button>
          )}
          {!isTerminal && confirmingCancel && (
            <span className="flex flex-wrap items-center gap-2">
              Cancel? The current stage will finish first.
              <Button variant="destructive" size="sm" className="rounded-full" onClick={handleCancel}>
                Yes, cancel
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="rounded-full"
                onClick={() => setConfirmingCancel(false)}
              >
                No
              </Button>
            </span>
          )}
          {isTerminal && (
            <Button variant="destructive" size="sm" className="rounded-full" onClick={handleDelete}>
              <Trash2 aria-hidden="true" />
              Delete
            </Button>
          )}
        </div>
      </header>

      <Card>
        <PipelineVisualization stages={job.stages} />
      </Card>

      {job.status === 'failed' && job.error && <ErrorState title="Failed" message={job.error} />}

      {job.research && (
        <Card>
          <ResearchSummary research={job.research} />
        </Card>
      )}

      {job.score && (
        <Card as="section" aria-labelledby="plan-heading" className="space-y-2">
          <h2 id="plan-heading" className="text-lg font-semibold">
            Plan
          </h2>
          <p className="text-sm">
            <span className="font-medium">Emotional arc:</span> {job.score.emotional_arc}
          </p>
          <p className="text-sm">
            <span className="font-medium">Archetype:</span> {job.score.archetype} ·{' '}
            <span className="font-medium">Music mood:</span> {job.score.music_mood}
          </p>
          <SceneTable scenes={job.score.scenes} />
          <RevisionHistory history={job.revision_history} />
        </Card>
      )}

      {(job.cost_estimate || job.cost_actual) && (
        <Card>
          <CostPanel estimate={job.cost_estimate} actual={job.cost_actual} />
        </Card>
      )}

      {job.review && (
        <Card>
          <CriticReview review={job.review} />
        </Card>
      )}

      {job.stages.assembly.status === 'completed' && jobId && (
        <Card as="section" aria-labelledby="result-heading" className="space-y-3">
          <h2 id="result-heading" className="text-lg font-semibold">
            Result
          </h2>
          <VideoPlayer jobId={jobId} />
          {visuals.data && (
            <SceneGallery jobId={jobId} runDir={job.run_dir} scenes={visuals.data.scenes} />
          )}
        </Card>
      )}
    </div>
  )
}
