import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StageCard } from './StageCard'

describe('StageCard', () => {
  it('shows the running status and the stage label', () => {
    render(<StageCard name="research" record={{ status: 'running' }} />)
    expect(screen.getByText('Research')).toBeInTheDocument()
    expect(screen.getByText('running')).toBeInTheDocument()
  })

  it('shows the skip reason when a stage is skipped', () => {
    render(<StageCard name="tts" record={{ status: 'skipped', reason: 'no_tts' }} />)
    expect(screen.getByText('no_tts')).toBeInTheDocument()
  })

  it('shows the error message when a stage failed', () => {
    render(<StageCard name="assembly" record={{ status: 'error', error: 'ffmpeg exploded' }} />)
    expect(screen.getByText('ffmpeg exploded')).toBeInTheDocument()
  })

  it('shows the duration once a stage has completed', () => {
    render(<StageCard name="director" record={{ status: 'completed', duration_s: 4.567 }} />)
    expect(screen.getByText('4.6s')).toBeInTheDocument()
  })
})
