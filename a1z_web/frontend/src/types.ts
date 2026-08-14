export type TaskStatus =
  | 'created' | 'starting' | 'ready' | 'running' | 'stopping'
  | 'completed' | 'failed' | 'faulted' | 'stopped'

export type HealthState = 'healthy' | 'degraded' | 'fault' | 'offline' | 'unknown'

export interface TaskInfo {
  task_id: string
  task_type: 'calibration' | 'pairing' | 'teleoperation' | 'recording' | 'inference'
  status: TaskStatus
  phase: string
  pid: number | null
  start_time: string
  end_time: string | null
  health: Record<string, HealthState>
  message: string | null
  mock: boolean
  metadata?: Record<string, unknown>
  record_phase?: 'ready' | 'recording' | 'saving' | 'resetting' | 'finished' | 'fault'
  episode_index?: number
  existing_episodes?: number
  add_episodes?: number
  total_after_session?: number
  frames?: number
  quick_next_armed?: boolean
  current_episode_invalid?: boolean
  last_trusted_episode?: number
  fault_reason?: string | null
}

export interface LogEntry {
  seq: number
  timestamp: string
  level: string
  source: string
  task_id: string
  message: string
}

export interface ApiFailure {
  error: { code: string; message: string; details: Record<string, unknown>; recoverable: boolean }
}

export interface DeviceInventory {
  mock: boolean
  can: Array<{ name: string; state: string; bitrate?: number }>
  leaders: Array<{ port: string; state: string }>
  cameras: Array<{ name: string; serial: string; state: string }>
  usb_can?: Array<{ usb_path: string; vendor_id: string; product_id: string; serial: string; product: string; supported: boolean }>
}

export interface CanInitializeResult {
  state: 'ready'
  simulation: boolean
  interface: { name: string; state: string; bitrate: number }
  message: string
}

export interface SystemHealth {
  mode: 'mock' | 'real'
  hardware_motion_enabled: boolean
  status: string
  resources: Record<string, string>
}

export interface RuntimeModeResult {
  mode: 'mock' | 'real'
  hardware_motion_enabled: boolean
  runtime_only: boolean
  message: string
}

export interface PreflightIssue {
  code: string
  resource: string
  title: string
  message: string
  action: string
  severity: 'blocking' | 'warning'
}

export interface PreflightReport {
  ready: boolean
  simulation: boolean
  workflow: 'calibration' | 'pairing' | 'teleoperation' | 'recording' | 'inference'
  mode: 'mock' | 'real'
  issues: PreflightIssue[]
  inventory: DeviceInventory
}

export interface PolicyReport {
  policy_path: string
  policy_type: string
  state_dim: number | null
  action_dim: number | null
  camera_keys: string[]
  image_shape: number[] | null
  fps: number | null
  processor: string
  device: string
  checks: Record<string, boolean>
  compatible: boolean
  compatibility_token: string | null
  hardware_connected: false
  mock: boolean
}

export interface RealtimeEvent {
  seq: number
  task_id: string | null
  type: string
  timestamp: string
  data: Record<string, unknown>
}
