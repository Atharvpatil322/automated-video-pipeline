import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { server } from '../test/setup'
import { renderWithProviders } from '../test/renderWithProviders'
import { BASE } from '../test/msw/handlers'
import { Home } from './Home'

describe('Home', () => {
  it('shows a live character counter for the topic field', async () => {
    renderWithProviders(<Home />)
    const topic = await screen.findByLabelText('Topic', { exact: false })
    await userEvent.type(topic, 'a brief topic')
    expect(screen.getByText('13/500')).toBeInTheDocument()
  })

  it('shows the API validation error inline instead of navigating', async () => {
    server.use(
      http.post(`${BASE}/api/v1/jobs`, () =>
        HttpResponse.json({ detail: 'unknown archetype: made-up' }, { status: 422 }),
      ),
    )
    renderWithProviders(<Home />)
    const topic = await screen.findByLabelText('Topic', { exact: false })
    await userEvent.type(topic, 'a topic that will fail validation')
    await userEvent.click(screen.getByRole('button', { name: 'Create job' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('unknown archetype: made-up')
    })
  })
})
