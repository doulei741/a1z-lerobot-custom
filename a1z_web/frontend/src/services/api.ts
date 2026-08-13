import type { ApiFailure, DeviceInventory, LogEntry, PolicyReport, TaskInfo } from '../types'

const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined
export const API_BASE = configuredBase?.replace(/\/$/, '') ?? ''

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public details: Record<string, unknown>,
    public recoverable: boolean,
    public status: number,
  ) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const payload = await response.json() as ApiFailure
    throw new ApiError(
      payload.error?.code ?? 'request_failed',
      payload.error?.message ?? `Request failed (${response.status})`,
      payload.error?.details ?? {},
      payload.error?.recoverable ?? false,
      response.status,
    )
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<{ mode: 'mock' | 'real'; status: string; resources: Record<string, string> }>('/system/health'),
  devices: () => request<DeviceInventory>('/devices'),
  tasks: () => request<TaskInfo[]>('/tasks'),
  task: (id: string) => request<TaskInfo>(`/tasks/${id}`),
  logs: (id: string, after = 0) => request<{ items: LogEntry[]; next_seq: number }>(`/tasks/${id}/logs?after=${after}`),
  stop: (id: string) => request<TaskInfo>(`/tasks/${id}/stop`, { method: 'POST', body: '{}' }),
  startTeleop: (body: Record<string, unknown>) => request<TaskInfo>('/teleop/start', { method: 'POST', body: JSON.stringify(body) }),
  startRecord: (body: Record<string, unknown>) => request<TaskInfo>('/record/start', { method: 'POST', body: JSON.stringify(body) }),
  recordCompatibility: (body: Record<string, unknown>) => request<{ compatible: boolean; new_dataset: boolean; existing_episodes: number; checks: Record<string, boolean> }>('/record/compatibility', { method: 'POST', body: JSON.stringify(body) }),
  recordAction: (id: string, action: string, actionId: string, episodeIndex: number) => request<TaskInfo & Record<string, unknown>>(`/record/${id}/${action}`, { method: 'POST', body: JSON.stringify({ client_action_id: actionId, episode_index: episodeIndex }) }),
  mockFrame: (id: string) => request<Record<string, unknown>>(`/mock/${id}/frame`, { method: 'POST', body: '{}' }),
  inspectPolicy: (policy_path: string, mode: 'single' | 'dual') => request<PolicyReport>('/inference/inspect-policy', { method: 'POST', body: JSON.stringify({ policy_path, mode }) }),
  startInference: (body: Record<string, unknown>) => request<TaskInfo>('/inference/start', { method: 'POST', body: JSON.stringify(body) }),
  startCalibration: (body: Record<string, unknown>) => request<TaskInfo>('/calibration/start', { method: 'POST', body: JSON.stringify(body) }),
  pairingProfiles: () => request<{ items: Array<{ profile_id: string; side: 'left' | 'right'; signs: number[]; scales: number[]; offsets_rad: number[] }> }>('/calibration/profiles'),
  calibrationStatus: (leaderId: string) => request<{ leader_id: string; exists: boolean; path: string }>(`/calibration/status?leader_id=${encodeURIComponent(leaderId)}`),
  calibrationAction: (id: string, action: string, actionId: string) => request<Record<string, unknown>>(`/calibration/${id}/${action}`, { method: 'POST', body: JSON.stringify({ client_action_id: actionId }) }),
  pairingCalculate: (body: Record<string, unknown>) => request<Record<string, unknown>>('/pairing/calculate', { method: 'POST', body: JSON.stringify(body) }),
  pairingRead: (body: Record<string, unknown>) => request<TaskInfo>('/pairing/read', { method: 'POST', body: JSON.stringify(body) }),
  pairingSave: (body: Record<string, unknown>) => request<Record<string, unknown>>('/pairing/save', { method: 'POST', body: JSON.stringify(body) }),
  pairingVerify: (body: Record<string, unknown>) => request<{ verified: boolean; errors_rad: number[]; tolerance_rad: number }>('/pairing/verify', { method: 'POST', body: JSON.stringify(body) }),
}

export function websocketUrl(lastSeq: number): string {
  if (configuredBase) {
    const url = new URL(configuredBase)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = '/ws/events'
    url.searchParams.set('last_seq', String(lastSeq))
    return url.toString()
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/events?last_seq=${lastSeq}`
}
