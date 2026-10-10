import type { ResearchResult } from '../api/types'

export function ResearchSummary({ research }: { research: ResearchResult }) {
  return (
    <section aria-labelledby="research-heading" className="space-y-2">
      <h2 id="research-heading" className="text-lg font-semibold">
        Research
      </h2>
      <p className="text-sm">{research.summary}</p>
      <p className="text-sm text-slate-500 dark:text-slate-400">Mood: {research.mood}</p>
      {research.key_facts.length > 0 && (
        <ul className="list-inside list-disc text-sm">
          {research.key_facts.map((fact, i) => (
            <li key={i}>{fact}</li>
          ))}
        </ul>
      )}
    </section>
  )
}
