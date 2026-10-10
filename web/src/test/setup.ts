import '@testing-library/jest-dom/vitest'

import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { defaultHandlers } from './msw/handlers'

export const server = setupServer(...defaultHandlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  sessionStorage.clear()
})
afterAll(() => server.close())
