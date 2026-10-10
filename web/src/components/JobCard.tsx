import { Film, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

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
      <div className="flex aspect-video items-center justify-center rounded-lg bg-muted">
        <Film className="h-6 w-6 text-muted-foreground/50" aria-hidden="true" />
      </div>
    )
  }
  return (
    <img
      src={fileUrl(settings, job.id, relativeToRunDir(firstImage.path, job.run_dir))}
      alt=""
      className="aspect-video w-full rounded-lg object-cover"
    />
  )
}

export function JobCard({ job, onDelete }: { job: JobSummary; onDelete: (id: string) => void }) {
  return (
    <Card className="gap-2 p-3">
      <Link to={`/jobs/${job.id}`} className="block space-y-2">
        <Thumbnail job={job} />
        <div className="flex items-center justify-between gap-2">
          <p className="truncate text-sm font-medium" title={job.topic}>
            {job.topic}
          </p>
          <StatusBadge status={job.status} />
        </div>
      </Link>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => onDelete(job.id)}
        aria-label={`Delete "${job.topic}"`}
        className="h-auto w-fit justify-start px-1.5 py-0.5 text-xs text-muted-foreground hover:text-destructive"
      >
        <Trash2 aria-hidden="true" />
        Delete
      </Button>
    </Card>
  )
}
