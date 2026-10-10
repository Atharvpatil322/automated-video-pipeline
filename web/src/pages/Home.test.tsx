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
    const topic = await screen.findByLabelText("What's it about?", { exact: false })
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
    const topic = await screen.findByLabelText("What's it about?", { exact: false })
    await userEvent.type(topic, 'a topic that will fail validation')
    await userEvent.click(screen.getByRole('button', { name: 'Create video' }))

    // Scoped by text rather than role="alert" alone - the OfflineBanner
    // (shadcn's Alert) also has role="alert" and is visible at the same
    // time (the mocked /health response reports offline: true).
    await waitFor(() => {
      expect(screen.getByText('unknown archetype: made-up')).toBeInTheDocument()
    })
  })
})
