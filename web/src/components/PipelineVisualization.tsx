import { ALL_STAGES, type StageRecord, type StageName } from '../api/types'
import { StageCard } from './StageCard'

export function PipelineVisualization({ stages }: { stages: Record<StageName, StageRecord> }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
      {ALL_STAGES.map((name) => (
        <StageCard key={name} name={name} record={stages[name]} />
      ))}
    </div>
  )
}
