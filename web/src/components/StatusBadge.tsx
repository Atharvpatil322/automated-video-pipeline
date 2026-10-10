import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import type { JobStatus, StageStatus } from '../api/types'

const COLORS: Record<string, string> = {
  queued: 'bg-secondary text-secondary-foreground',
  pending: 'bg-secondary text-secondary-foreground',
  running: 'bg-primary/15 text-primary dark:bg-primary/25',
  completed: 'bg-[var(--color-success)]/15 text-[var(--color-success)]',
  skipped: 'bg-muted text-muted-foreground',
  failed: 'bg-destructive/10 text-destructive',
  error: 'bg-destructive/10 text-destructive',
  cancelled: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
}

export function StatusBadge({ status }: { status: JobStatus | StageStatus }) {
  return <Badge className={cn('border-transparent', COLORS[status] ?? COLORS.pending)}>{status}</Badge>
}
