import {
  Check,
  ClipboardCheck,
  Clapperboard,
  Film,
  Image,
  Loader2,
  type LucideIcon,
  Mic,
  Minus,
  Search,
  X,
} from 'lucide-react'

import { ALL_STAGES, type StageName, type StageRecord, type StageStatus } from '../api/types'

const STAGE_META: Record<StageName, { label: string; icon: LucideIcon }> = {
  research: { label: 'Research', icon: Search },
  director: { label: 'Director', icon: Clapperboard },
  tts: { label: 'Voiceover', icon: Mic },
  visuals: { label: 'Visuals', icon: Image },
  assembly: { label: 'Assembly', icon: Film },
  critic: { label: 'Critic', icon: ClipboardCheck },
}

function dotClasses(status: StageStatus): string {
  switch (status) {
    case 'completed':
      return 'border-[var(--color-success)] bg-[var(--color-success)] text-white'
    case 'running':
      return 'border-primary bg-primary text-primary-foreground'
    case 'error':
      return 'border-destructive bg-destructive text-white'
    case 'skipped':
      return 'border-border bg-muted text-muted-foreground'
    default:
      return 'border-border bg-card text-muted-foreground'
  }
}

function StatusIcon({ status, Icon }: { status: StageStatus; Icon: LucideIcon }) {
  if (status === 'completed') return <Check className="h-4 w-4" aria-hidden="true" />
  if (status === 'running') return <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
  if (status === 'error') return <X className="h-4 w-4" aria-hidden="true" />
  if (status === 'skipped') return <Minus className="h-4 w-4" aria-hidden="true" />
  return <Icon className="h-4 w-4" aria-hidden="true" />
}

function describe(record: StageRecord): string | null {
  if (record.status === 'error') return record.error ?? 'failed'
  if (record.status === 'skipped') return record.reason ?? null
  if (record.detail) {
    const entries = Object.entries(record.detail)
    if (entries.length > 0) return entries.map(([k, v]) => `${k}: ${String(v)}`).join(', ')
  }
  return null
}

export function PipelineVisualization({ stages }: { stages: Record<StageName, StageRecord> }) {
  return (
    <ol aria-live="polite" className="flex flex-wrap gap-x-1 gap-y-4 sm:flex-nowrap">
      {ALL_STAGES.map((name, i) => {
        const record = stages[name]
        const { label, icon } = STAGE_META[name]
        const detail = describe(record)
        return (
          <li key={name} className="flex min-w-0 flex-1 items-start">
            <div className="flex min-w-0 flex-col items-center gap-1 text-center">
              <span
                title={`${label}: ${record.status}`}
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 ${dotClasses(record.status)}`}
              >
                <StatusIcon status={record.status} Icon={icon} />
              </span>
              <span className="text-xs font-medium">{label}</span>
              {detail && (
                <span className="max-w-[7rem] truncate text-[11px] text-muted-foreground" title={detail}>
                  {detail}
                </span>
              )}
              {record.duration_s != null && (
                <span className="text-[11px] text-muted-foreground/70">
                  {record.duration_s.toFixed(1)}s
                </span>
              )}
            </div>
            {i < ALL_STAGES.length - 1 && (
              <div
                aria-hidden="true"
                className={`mt-[18px] h-0.5 min-w-4 flex-1 ${
                  record.status === 'completed' ? 'bg-[var(--color-success)]' : 'bg-border'
                }`}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}
