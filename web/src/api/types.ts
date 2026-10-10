// Mirrors app/schema/*.py and app/server/*.py response shapes. Kept hand
// written (not generated) since the backend has no OpenAPI export step yet.

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
export type StageName = 'research' | 'director' | 'tts' | 'visuals' | 'assembly' | 'critic'
export type StageStatus = 'pending' | 'running' | 'completed' | 'skipped' | 'error'

export const ALL_STAGES: StageName[] = [
  'research',
  'director',
  'tts',
  'visuals',
  'assembly',
  'critic',
]

export interface StageRecord {
  status: StageStatus
  detail?: Record<string, unknown> | null
  reason?: string | null
  error?: string | null
  started_at?: string | null
  duration_s?: number | null
}

export type VisualType = 'ai_image' | 'ai_video' | 'stock_image' | 'stock_video' | 'text_card'
export type Motion = 'zoom_in' | 'zoom_out' | 'pan_right' | 'pan_left' | 'static'
export type Transition = 'none' | 'crossfade' | 'slide_left' | 'slide_right' | 'wipe' | 'flip'

export interface Scene {
  visual_type: VisualType
  visual_prompt: string
  motion: Motion
  script_line: string
  transition: Transition | null
}

export interface DirectorScore {
  emotional_arc: string
  archetype: string
  music_mood: string
  scenes: Scene[]
}

export interface ResearchResult {
  summary: string
  key_facts: string[]
  mood: string
  sources: string[]
}

export interface CritiqueResult {
  score: number
  strengths: string[]
  weaknesses: string[]
  revision_needed: boolean
  revision_instructions: string | null
  weakest_scene_index: number | null
}

export interface RevisionHistoryEntry {
  round: number
  score: number
  [key: string]: unknown
}

export interface CostBreakdown {
  llm: number
  tts: number
  images: number
  video: number
  stock: number
  vlm: number
}

export interface CostEstimate {
  breakdown: CostBreakdown
  notes: string[]
}

export interface CostActual {
  breakdown: CostBreakdown
}

export interface JobOptions {
  topic: string
  archetype: string
  platform: string
  direction?: string | null
  tts_provider: string
  image_provider: string
  no_tts: boolean
  no_visuals: boolean
  no_video: boolean
  no_music: boolean
  no_critic: boolean
  score?: DirectorScore | null
}

export interface JobDocument {
  id: string
  status: JobStatus
  options: JobOptions
  stages: Record<StageName, StageRecord>
  score: DirectorScore | null
  research: ResearchResult | null
  review: CritiqueResult | null
  revision_history: RevisionHistoryEntry[]
  cost_estimate: CostEstimate | null
  cost_actual: CostActual | null
  cancel_requested: boolean
  error: string | null
  run_dir: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export interface JobSummary {
  id: string
  status: JobStatus
  topic: string
  created_at: string
  updated_at: string
  // GET /jobs returns the full Mongo document (app/server/routes/jobs.py's
  // `_public_view` doesn't actually narrow it to JobSummary's Python
  // fields) - run_dir is needed client-side to turn visuals.json's
  // absolute scene paths back into paths relative to it.
  run_dir?: string | null
}

export interface JobCreateRequest {
  topic: string
  archetype: string
  platform: string
  direction?: string | null
  tts_provider: string
  image_provider: string
  no_tts: boolean
  no_visuals: boolean
  no_video: boolean
  no_music: boolean
  no_critic: boolean
  keys: Record<string, string>
}

export interface JobCreateResponse {
  id: string
  topic: string
  archetype: string
  status: JobStatus
}

export interface HealthResponse {
  status: string
  offline: boolean
}

export interface ProvidersResponse {
  llm: string[]
  tts: string[]
  image: string[]
  stock: string[]
  video: string[]
}

export type SceneVisualStatus = 'generated' | 'fallback' | 'failed' | 'no_asset'

export interface SceneVisualResult {
  scene_index: number
  visual_type: VisualType
  path: string | null
  status: SceneVisualStatus
  attempts: number
  fallback_reason?: string | null
  method?: string | null
  provider?: string | null
  query?: string | null
  confidence?: number | null
  attribution?: string | null
  motion_override?: Motion | null
}

export interface VisualsResult {
  scenes: SceneVisualResult[]
}

export interface ApiError {
  detail: string | { msg: string }[]
}
