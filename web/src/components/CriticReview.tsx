import { ClipboardCheck } from 'lucide-react'

import type { CritiqueResult } from '../api/types'

export function CriticReview({ review }: { review: CritiqueResult }) {
  return (
    <section aria-labelledby="critic-heading" className="space-y-2">
      <h2 id="critic-heading" className="flex items-center gap-2 text-lg font-semibold">
        <ClipboardCheck className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        Critic review
        <span className="ml-auto rounded-full bg-accent px-2.5 py-0.5 text-base font-bold text-accent-foreground">
          {review.score.toFixed(1)}/10
        </span>
      </h2>
      {review.strengths.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-green-700 dark:text-green-400">Strengths</h3>
          <ul className="list-inside list-disc text-sm">
            {review.strengths.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}
      {review.weaknesses.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-amber-700 dark:text-amber-400">Weaknesses</h3>
          <ul className="list-inside list-disc text-sm">
            {review.weaknesses.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
