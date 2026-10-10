import type { RevisionHistoryEntry } from '../api/types'

export function RevisionHistory({ history }: { history: RevisionHistoryEntry[] }) {
  if (history.length === 0) return null
  return (
    <div className="space-y-1">
      <h3 className="text-sm font-semibold">Revision history</h3>
      <ul className="text-sm text-slate-600 dark:text-slate-300">
        {history.map((entry, i) => (
          <li key={i}>
            Round {entry.round}: critic score {entry.score}
          </li>
        ))}
      </ul>
    </div>
  )
}
