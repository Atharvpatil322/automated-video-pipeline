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
  return (
    <section aria-labelledby="cost-heading" className="space-y-2">
      <h2 id="cost-heading" className="text-lg font-semibold">
        Cost
      </h2>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-slate-500 dark:border-slate-800 dark:text-slate-400">
            <th scope="col" className="py-1">Stage</th>
            <th scope="col" className="py-1">Estimate</th>
            <th scope="col" className="py-1">Actual</th>
          </tr>
        </thead>
        <tbody>
          {STAGES.map(({ key, label }) => (
            <tr key={key} className="border-b border-slate-100 dark:border-slate-900">
              <td className="py-1">{label}</td>
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
        <ul className="text-xs text-slate-500 dark:text-slate-400">
          {estimate.notes.map((note, i) => (
            <li key={i}>{note}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
