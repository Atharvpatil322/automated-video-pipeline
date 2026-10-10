import { http, HttpResponse } from 'msw'

import type { HealthResponse, JobDocument, ProvidersResponse } from '../../api/types'

// Relative paths match any origin - simpler than pinning a BASE that has
// to agree with jsdom's test URL (vitest's default is localhost:3000, not
// plain localhost).
export const BASE = ''

export function makeJob(overrides: Partial<JobDocument> = {}): JobDocument {
  return {
    id: 'job-1',
    status: 'running',
    options: {
      topic: 'test topic',
      archetype: 'infographic',
      platform: 'youtube',
      direction: null,
      tts_provider: 'elevenlabs',
      image_provider: 'openai',
      no_tts: false,
      no_visuals: false,
      no_video: false,
      no_music: false,
      no_critic: false,
    },
    stages: {
      research: { status: 'completed' },
      director: { status: 'completed' },
      tts: { status: 'running' },
      visuals: { status: 'pending' },
      assembly: { status: 'pending' },
      critic: { status: 'pending' },
    },
    score: null,
    research: null,
    review: null,
    revision_history: [],
    cost_estimate: null,
    cost_actual: null,
    cancel_requested: false,
    error: null,
    run_dir: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    started_at: '2026-01-01T00:00:00Z',
    finished_at: null,
    ...overrides,
  }
}

export const defaultHandlers = [
  http.get(`${BASE}/api/v1/health`, () =>
    HttpResponse.json<HealthResponse>({ status: 'ok', offline: true }),
  ),
  http.get(`${BASE}/api/v1/archetypes`, () => HttpResponse.json(['infographic', 'cinematic_documentary'])),
  http.get(`${BASE}/api/v1/platforms`, () => HttpResponse.json(['youtube', 'tiktok'])),
  http.get(`${BASE}/api/v1/providers`, () =>
    HttpResponse.json<ProvidersResponse>({
      llm: ['groq', 'offline'],
      tts: ['elevenlabs', 'openai', 'offline'],
      image: ['openai', 'gemini', 'offline'],
      stock: ['pexels', 'pixabay', 'offline'],
      video: ['fal', 'offline'],
    }),
  ),
  http.get(`${BASE}/api/v1/jobs`, () => HttpResponse.json([])),
  http.get(`${BASE}/api/v1/jobs/:id`, () => HttpResponse.json(makeJob())),
]
