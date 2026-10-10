import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { StageName, StageRecord } from '../api/types'
import { PipelineVisualization } from './PipelineVisualization'

function stages(overrides: Partial<Record<StageName, StageRecord>>): Record<StageName, StageRecord> {
  const base: Record<StageName, StageRecord> = {
    research: { status: 'pending' },
    director: { status: 'pending' },
    tts: { status: 'pending' },
    visuals: { status: 'pending' },
    assembly: { status: 'pending' },
    critic: { status: 'pending' },
  }
  return { ...base, ...overrides }
}

describe('PipelineVisualization', () => {
  it('labels every stage and shows its status', () => {
    render(<PipelineVisualization stages={stages({ research: { status: 'running' } })} />)
    expect(screen.getByText('Research')).toBeInTheDocument()
    expect(screen.getByTitle('Research: running')).toBeInTheDocument()
  })

  it('shows the skip reason for a skipped stage', () => {
    render(<PipelineVisualization stages={stages({ tts: { status: 'skipped', reason: 'no_tts' } })} />)
    expect(screen.getByText('no_tts')).toBeInTheDocument()
  })

  it('shows the error message for a failed stage', () => {
    render(
      <PipelineVisualization
        stages={stages({ assembly: { status: 'error', error: 'ffmpeg exploded' } })}
      />,
    )
    expect(screen.getByText('ffmpeg exploded')).toBeInTheDocument()
  })

  it('shows the duration once a stage has completed', () => {
    render(
      <PipelineVisualization stages={stages({ director: { status: 'completed', duration_s: 4.567 } })} />,
    )
    expect(screen.getByText('4.6s')).toBeInTheDocument()
  })
})
