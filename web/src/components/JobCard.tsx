import { Link } from 'react-router-dom'

import { fileUrl } from '../api/client'
import { useVisuals } from '../api/queries'
import type { JobSummary } from '../api/types'
import { relativeToRunDir } from '../lib/assetPath'
import { useSettings } from '../state/settings'
import { StatusBadge } from './StatusBadge'

const VISUALS_AVAILABLE_AFTER = new Set(['running', 'completed', 'failed', 'cancelled'])

function Thumbnail({ job }: { job: JobSummary }) {
  const { settings } = useSettings()
  const { data } = useVisuals(job.id, VISUALS_AVAILABLE_AFTER.has(job.status))
  const firstImage = data?.scenes.find(
    (scene) => scene.path && !scene.path.toLowerCase().endsWith('.mp4'),
  )
  if (!firstImage?.path) {
    return (
      <div className="flex aspect-video items-center justify-center rounded-md bg-slate-100 text-xs text-slate-400 dark:bg-slate-900">
        no preview
      </div>
    )
  }
  return (
    <img
      src={fileUrl(settings, job.id, relativeToRunDir(firstImage.path, job.run_dir))}
      alt=""
      className="aspect-video w-full rounded-md object-cover"
    />
  )
}

export function JobCard({ job, onDelete }: { job: JobSummary; onDelete: (id: string) => void }) {
  return (
    <div className="space-y-2 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
      <Thumbnail job={job} />
      <div className="flex items-center justify-between gap-2">
        <p className="truncate font-medium" title={job.topic}>
          {job.topic}
        </p>
        <StatusBadge status={job.status} />
      </div>
      <div className="flex gap-2 text-sm">
        <Link
          to={`/jobs/${job.id}`}
          className="rounded-md border border-slate-300 px-2 py-1 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"
        >
          Open
        </Link>
        <button
          type="button"
          onClick={() => onDelete(job.id)}
          className="rounded-md border border-red-300 px-2 py-1 text-red-700 hover:bg-red-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950"
        >
          Delete
        </button>
      </div>
    </div>
  )
}
