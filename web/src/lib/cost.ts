import type { CostActual, CostBreakdown, CostEstimate } from '../api/types'

// `total` is a @property on the Pydantic models (CostEstimate/CostActual),
// not a model field, so it's never present in the JSON the API serializes
// - every consumer sums the breakdown itself. This is the one place that
// does it, so the cost panel and the gallery job cards never disagree.
export function sumBreakdown(breakdown: CostBreakdown | null | undefined): number {
  if (!breakdown) return 0
  return (
    breakdown.llm + breakdown.tts + breakdown.images + breakdown.video + breakdown.stock + breakdown.vlm
  )
}

export function estimateTotal(estimate: CostEstimate | null | undefined): number {
  return sumBreakdown(estimate?.breakdown)
}

export function actualTotal(actual: CostActual | null | undefined): number {
  return sumBreakdown(actual?.breakdown)
}

export function formatUsd(amount: number): string {
  return `$${amount.toFixed(4)}`
}
