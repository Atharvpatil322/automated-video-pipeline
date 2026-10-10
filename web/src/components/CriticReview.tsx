import type { CritiqueResult } from '../api/types'

export function CriticReview({ review }: { review: CritiqueResult }) {
  return (
    <section aria-labelledby="critic-heading" className="space-y-2">
      <h2 id="critic-heading" className="text-lg font-semibold">
        Critic review
      </h2>
      <p className="text-2xl font-bold">{review.score.toFixed(1)}/10</p>
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
