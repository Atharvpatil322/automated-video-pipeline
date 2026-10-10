import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { useSettings } from '../state/settings'
import { apiFetch } from './client'
import type {
  HealthResponse,
  JobCreateRequest,
  JobCreateResponse,
  JobDocument,
  JobSummary,
  ProvidersResponse,
  VisualsResult,
} from './types'

const API = '/api/v1'

export function useHealth() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['health', settings.apiBaseUrl],
    queryFn: () => apiFetch<HealthResponse>(settings, `${API}/health`),
    staleTime: 60_000,
  })
}

export function useArchetypes() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['archetypes', settings.apiBaseUrl],
    queryFn: () => apiFetch<string[]>(settings, `${API}/archetypes`),
    staleTime: 60_000,
  })
}

export function usePlatforms() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['platforms', settings.apiBaseUrl],
    queryFn: () => apiFetch<string[]>(settings, `${API}/platforms`),
    staleTime: 60_000,
  })
}

export function useProviders() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['providers', settings.apiBaseUrl],
    queryFn: () => apiFetch<ProvidersResponse>(settings, `${API}/providers`),
    staleTime: 60_000,
  })
}

const ACTIVE_STATUSES = new Set(['queued', 'running'])
const GALLERY_AUTO_REFRESH_MS = 3000

export function useJobs() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['jobs', settings.apiBaseUrl],
    queryFn: () => apiFetch<JobSummary[]>(settings, `${API}/jobs`),
    refetchInterval: (query) => {
      const jobs = query.state.data as JobSummary[] | undefined
      const anyActive = jobs?.some((job) => ACTIVE_STATUSES.has(job.status)) ?? false
      return anyActive ? GALLERY_AUTO_REFRESH_MS : false
    },
  })
}

export function useJob(jobId: string | undefined, options: { refetchInterval?: number } = {}) {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['job', settings.apiBaseUrl, jobId],
    queryFn: () => apiFetch<JobDocument>(settings, `${API}/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: options.refetchInterval,
  })
}

export function useVisuals(jobId: string | undefined, enabled: boolean) {
  const { settings } = useSettings()
  return useQuery({
    queryKey: ['visuals', settings.apiBaseUrl, jobId],
    queryFn: () =>
      apiFetch<VisualsResult>(settings, `${API}/jobs/${jobId}/files/visuals.json`),
    enabled: Boolean(jobId) && enabled,
    retry: false,
  })
}

export function useCreateJob() {
  const { settings } = useSettings()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: JobCreateRequest) =>
      apiFetch<JobCreateResponse>(settings, `${API}/jobs`, {
        method: 'POST',
        body: JSON.stringify(request),
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useCancelJob() {
  const { settings } = useSettings()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) =>
      apiFetch(settings, `${API}/jobs/${jobId}/cancel`, { method: 'POST' }),
    onSuccess: (_data, jobId) => {
      void queryClient.invalidateQueries({ queryKey: ['job', settings.apiBaseUrl, jobId] })
    },
  })
}

export function useDeleteJob() {
  const { settings } = useSettings()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) =>
      apiFetch(settings, `${API}/jobs/${jobId}`, { method: 'DELETE' }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}
