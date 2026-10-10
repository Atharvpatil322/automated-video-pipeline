import type { StageName, StageRecord } from '../api/types'
import { StatusBadge } from './StatusBadge'

const LABELS: Record<StageName, string> = {
  research: 'Research',
  director: 'Director',
  tts: 'Voiceover',
  visuals: 'Visuals',
  assembly: 'Assembly',
  critic: 'Critic',
}

function describe(record: StageRecord): string | null {
  if (record.status === 'error') return record.error ?? 'failed'
  if (record.status === 'skipped') return record.reason ?? null
  if (record.detail) {
    const entries = Object.entries(record.detail)
    if (entries.length > 0) {
      return entries.map(([k, v]) => `${k}: ${String(v)}`).join(', ')
    }
  }
  return null
}

export function StageCard({ name, record }: { name: StageName; record: StageRecord }) {
  const detail = describe(record)
  return (
    <div
      aria-live="polite"
      className="flex flex-col gap-1 rounded-lg border border-slate-200 p-3 dark:border-slate-800"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{LABELS[name]}</span>
        <StatusBadge status={record.status} />
      </div>
      {detail && <p className="truncate text-xs text-slate-500 dark:text-slate-400" title={detail}>{detail}</p>}
      {record.duration_s != null && (
        <p className="text-xs text-slate-400 dark:text-slate-500">{record.duration_s.toFixed(1)}s</p>
      )}
    </div>
  )
}
