import '@testing-library/jest-dom/vitest'

import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll } from 'vitest'

import { defaultHandlers } from './msw/handlers'

// jsdom has no ResizeObserver/PointerEvent capture APIs; several Radix
// primitives (Select, Tooltip) use them for sizing/positioning. Stubs are
// enough for interaction tests - no layout actually happens in jsdom.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver

if (!Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false
}
if (!Element.prototype.setPointerCapture) {
  Element.prototype.setPointerCapture = () => {}
}
if (!Element.prototype.releasePointerCapture) {
  Element.prototype.releasePointerCapture = () => {}
}
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {}
}

export const server = setupServer(...defaultHandlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  sessionStorage.clear()
})
afterAll(() => server.close())
