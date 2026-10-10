import type { JobStatus, StageStatus } from '../api/types'

const COLORS: Record<string, string> = {
  queued: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  pending: 'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  running: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300',
  completed: 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300',
  skipped: 'bg-slate-100 text-slate-500 dark:bg-slate-900 dark:text-slate-400',
  failed: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  error: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300',
  cancelled: 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300',
}

export function StatusBadge({ status }: { status: JobStatus | StageStatus }) {
  const classes = COLORS[status] ?? COLORS.pending
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {status}
    </span>
  )
}
