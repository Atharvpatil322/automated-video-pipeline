import { Search } from 'lucide-react'

import type { ResearchResult } from '../api/types'

export function ResearchSummary({ research }: { research: ResearchResult }) {
  return (
    <section aria-labelledby="research-heading" className="space-y-2">
      <h2 id="research-heading" className="flex items-center gap-2 text-lg font-semibold">
        <Search className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        Research
      </h2>
      <p className="text-sm">{research.summary}</p>
      <p className="text-sm text-muted-foreground">Mood: {research.mood}</p>
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
