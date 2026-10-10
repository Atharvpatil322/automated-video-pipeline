import type { SettingsState } from '../state/settings'
import type { ApiError as ApiErrorBody } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

function authHeaders(settings: SettingsState): HeadersInit {
  return settings.apiToken ? { Authorization: `Bearer ${settings.apiToken}` } : {}
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) return body.detail.map((d) => d.msg).join('; ')
  } catch {
    // body wasn't JSON - fall through to the generic message
  }
  return `request failed with status ${response.status}`
}

export async function apiFetch<T>(
  settings: SettingsState,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${settings.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      ...authHeaders(settings),
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

/** Build a src URL for the files route. A query-param token fallback is
 * used only here - plain <video>/<img> tags can't send Authorization
 * headers, so this is the one place the backend accepts the token in the
 * URL instead (app/server/auth.py's require_api_token_or_query).
 */
export function fileUrl(settings: SettingsState, jobId: string, filePath: string): string {
  const base = `${settings.apiBaseUrl}/api/v1/jobs/${jobId}/files/${filePath}`
  return settings.apiToken ? `${base}?token=${encodeURIComponent(settings.apiToken)}` : base
}
