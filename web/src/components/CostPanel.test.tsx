import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CostActual, CostEstimate } from '../api/types'
import { CostPanel } from './CostPanel'

const estimate: CostEstimate = {
  breakdown: { llm: 0.01, tts: 0.1, images: 0.2, video: 0.3, stock: 0, vlm: 0.04 },
  notes: ['stock disabled, using AI image fallback'],
}

const actual: CostActual = {
  breakdown: { llm: 0.012, tts: 0.1, images: 0.21, video: 0.3, stock: 0, vlm: 0.04 },
}

describe('CostPanel', () => {
  it('renders nothing when there is no cost data yet', () => {
    const { container } = render(<CostPanel estimate={null} actual={null} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('sums the breakdown into matching estimate and actual totals', () => {
    render(<CostPanel estimate={estimate} actual={actual} />)
    // 0.01 + 0.1 + 0.2 + 0.3 + 0 + 0.04 = 0.65
    expect(screen.getByText('$0.6500')).toBeInTheDocument()
    // 0.012 + 0.1 + 0.21 + 0.3 + 0 + 0.04 = 0.662
    expect(screen.getByText('$0.6620')).toBeInTheDocument()
  })

  it('shows estimate notes', () => {
    render(<CostPanel estimate={estimate} actual={null} />)
    expect(screen.getByText('stock disabled, using AI image fallback')).toBeInTheDocument()
  })
})
