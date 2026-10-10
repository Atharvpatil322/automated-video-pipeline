import { DollarSign } from 'lucide-react'

import type { CostActual, CostEstimate } from '../api/types'
import { actualTotal, estimateTotal, formatUsd } from '../lib/cost'

const STAGES: { key: keyof CostEstimate['breakdown']; label: string }[] = [
  { key: 'llm', label: 'LLM' },
  { key: 'tts', label: 'Voiceover' },
  { key: 'images', label: 'Images' },
  { key: 'video', label: 'Video' },
  { key: 'stock', label: 'Stock' },
  { key: 'vlm', label: 'Verification' },
]

export function CostPanel({
  estimate,
  actual,
}: {
  estimate: CostEstimate | null
  actual: CostActual | null
}) {
  if (!estimate && !actual) return null

  const total = actual ? actualTotal(actual) : estimateTotal(estimate)
  const label = actual ? 'Cost so far' : 'Estimated cost'

  return (
    <section aria-labelledby="cost-heading" className="space-y-3">
      <h2 id="cost-heading" className="flex items-center gap-2 text-lg font-semibold">
        <DollarSign className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        {label}
        <span className="ml-auto text-xl font-bold tabular-nums text-primary">{formatUsd(total)}</span>
      </h2>

      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
          Breakdown by stage
        </summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr className="border-b text-muted-foreground">
              <th scope="col" className="py-1">Stage</th>
              <th scope="col" className="py-1">Estimate</th>
              <th scope="col" className="py-1">Actual</th>
            </tr>
          </thead>
          <tbody>
            {STAGES.map(({ key, label: stageLabel }) => (
              <tr key={key} className="border-b border-border/60">
                <td className="py-1">{stageLabel}</td>
                <td className="py-1">{formatUsd(estimate?.breakdown[key] ?? 0)}</td>
                <td className="py-1">{formatUsd(actual?.breakdown[key] ?? 0)}</td>
              </tr>
            ))}
            <tr className="font-semibold">
              <td className="py-1">Total</td>
              <td className="py-1">{formatUsd(estimateTotal(estimate))}</td>
              <td className="py-1">{formatUsd(actualTotal(actual))}</td>
            </tr>
          </tbody>
        </table>
        {estimate?.notes && estimate.notes.length > 0 && (
          <ul className="mt-2 text-xs text-muted-foreground">
            {estimate.notes.map((note, i) => (
              <li key={i}>{note}</li>
            ))}
          </ul>
        )}
      </details>
    </section>
  )
}
