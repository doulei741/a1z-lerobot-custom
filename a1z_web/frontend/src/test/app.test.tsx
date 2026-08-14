import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'
import { usePlatformStore } from '../stores/platform'

const jsonResponse = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'mock', status: 'healthy', resources: {} })
    if (url.includes('/devices')) return jsonResponse({ mock: true, can: [], leaders: [], cameras: [] })
    if (/\/tasks\/[^/]+$/.test(url)) return jsonResponse({ task_id: 'record-test123', task_type: 'recording', status: 'running', phase: 'recording', health: {}, mock: true })
    if (url.includes('/tasks')) return jsonResponse([])
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    return jsonResponse({})
  }))
})

afterEach(() => { cleanup(); usePlatformStore.getState().setActiveTask(null); vi.unstubAllGlobals() })

test('renders exactly the four workflow navigation items', async () => {
  render(<App initialPath="/calibration" disableRealtime />)
  expect(await screen.findByRole('heading', { name: '机械臂校准' })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /机械臂校准/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /遥控操作/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /数据录制/ })).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /模型推理/ })).toBeInTheDocument()
  expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
})

test('inference start stays gated until compatibility passes', async () => {
  render(<App initialPath="/inference" disableRealtime />)
  const run = await screen.findByRole('button', { name: '开始安全推理' })
  expect(run).toBeDisabled()
  expect(screen.getByText(/连接硬件之前/)).toBeInTheDocument()
})

test('recording exposes domain actions instead of keyboard directions', async () => {
  render(<App initialPath="/recording" disableRealtime />)
  expect(await screen.findByRole('button', { name: '开始录制任务' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '提前结束并保存' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '丢弃本轮并重录' })).toBeDisabled()
  expect(screen.getByRole('button', { name: '快速开始下一轮' })).toBeDisabled()
  expect(screen.queryByText(/方向键/)).not.toBeInTheDocument()
})

test('global safe stop remains visible after route navigation', async () => {
  const user = userEvent.setup()
  render(<App initialPath="/teleoperation" disableRealtime />)
  expect(await screen.findByRole('button', { name: '软件停止' })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: /数据录制/ }))
  expect(screen.getByRole('button', { name: '软件停止' })).toBeInTheDocument()
  expect(screen.getByText(/软件停止 ≠ 硬件急停/)).toBeInTheDocument()
})

test('active task id survives route navigation', async () => {
  const user = userEvent.setup()
  usePlatformStore.getState().setActiveTask('record-test123', 'recording')
  render(<App initialPath="/recording" disableRealtime />)
  expect(await screen.findByText('record-test123')).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: /机械臂校准/ }))
  expect(screen.getByText('record-test123')).toBeInTheDocument()
})

test('a terminal task restored from a previous browser session is archived without a fault popup', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'real', hardware_motion_enabled: true, status: 'healthy', resources: {} })
    if (/\/tasks\/stale-teleop$/.test(url)) return jsonResponse({ task_id: 'stale-teleop', task_type: 'teleoperation', status: 'faulted', phase: 'fault', health: {}, mock: false, message: 'Backend restarted while this task was active; verify hardware manually' })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/devices')) return jsonResponse({ mock: false, can: [], leaders: [], cameras: [] })
    return jsonResponse([])
  }))
  usePlatformStore.setState({ activeTaskId: 'stale-teleop', activeTaskType: 'teleoperation' })

  render(<App initialPath="/teleoperation" disableRealtime />)

  await waitFor(() => expect(usePlatformStore.getState().activeTaskId).toBeNull())
  expect(screen.queryByRole('heading', { name: '设备检查未通过' })).not.toBeInTheDocument()
})

test('a task started in the current page still reports an immediate failure', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'real', hardware_motion_enabled: true, status: 'healthy', resources: {} })
    if (/\/tasks\/current-teleop$/.test(url)) return jsonResponse({ task_id: 'current-teleop', task_type: 'teleoperation', status: 'failed', phase: 'failed', health: {}, mock: false, message: 'camera unavailable' })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/devices')) return jsonResponse({ mock: false, can: [], leaders: [], cameras: [] })
    return jsonResponse([])
  }))
  render(<App initialPath="/teleoperation" disableRealtime />)

  act(() => usePlatformStore.getState().setActiveTask('current-teleop', 'teleoperation'))

  expect(await screen.findByRole('heading', { name: '设备检查未通过' })).toBeInTheDocument()
  expect(screen.getByText('camera unavailable')).toBeInTheDocument()

  await userEvent.click(screen.getByRole('button', { name: '关闭' }))
  await waitFor(() => expect(usePlatformStore.getState().activeTaskId).toBeNull())
})

test('record controls refresh frames and keep normal stop available while recording', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'mock', status: 'healthy', resources: {} })
    if (/\/tasks\/record-live$/.test(url)) return jsonResponse({
      task_id: 'record-live', task_type: 'recording', status: 'ready', phase: 'ready',
      record_phase: 'recording', frames: 3, episode_index: 0, remaining_time_s: 42,
      episode_time_s: 60, health: {}, mock: true,
    })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/devices')) return jsonResponse({ mock: true, can: [], leaders: [], cameras: [] })
    return jsonResponse([])
  }))
  usePlatformStore.getState().setActiveTask('record-live', 'recording')

  render(<App initialPath="/recording" disableRealtime />)

  expect(await screen.findByText('3')).toBeInTheDocument()
  expect(screen.getByText('00:42')).toBeInTheDocument()
  expect(screen.getByText('本轮剩余')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '提前结束并保存' })).toBeEnabled()
  expect(screen.getByRole('button', { name: '正常停止整个任务' })).toBeEnabled()
})

test('recording explains why controls are locked during atomic video saving', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'mock', status: 'healthy', resources: {} })
    if (/\/tasks\/record-saving$/.test(url)) return jsonResponse({
      task_id: 'record-saving', task_type: 'recording', status: 'ready', phase: 'saving',
      record_phase: 'saving', frames: 213, episode_index: 0, add_episodes: 2,
      health: {}, mock: true,
    })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/devices')) return jsonResponse({ mock: true, can: [], leaders: [], cameras: [] })
    return jsonResponse([])
  }))
  usePlatformStore.getState().setActiveTask('record-saving', 'recording')

  render(<App initialPath="/recording" disableRealtime />)

  expect(await screen.findByText(/正在保存 Episode 并编码视频/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '正常停止整个任务' })).toBeDisabled()
})

test('teleoperation preflight blocks task start and shows recovery steps', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'real', status: 'degraded', resources: {} })
    if (url.includes('/teleop/preflight')) return jsonResponse({
      ready: false,
      simulation: false,
      workflow: 'teleoperation',
      mode: 'real',
      inventory: { mock: false, can: [], leaders: [], cameras: [] },
      issues: [{
        code: 'can_missing', resource: 'can0', title: 'can0 不存在',
        message: 'Left Follower 需要 can0。', action: '运行 setup.sh can0。', severity: 'blocking',
      }],
    })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/tasks')) return jsonResponse([])
    return jsonResponse({})
  }))
  const user = userEvent.setup()
  render(<App initialPath="/teleoperation" disableRealtime />)

  await user.click(await screen.findByRole('checkbox', { name: /确认运动安全检查/ }))
  await user.click(screen.getByRole('button', { name: 'Start Teleoperation' }))

  expect(await screen.findByRole('heading', { name: '设备检查未通过' })).toBeInTheDocument()
  expect(screen.getByText(/运行 setup\.sh can0/)).toBeInTheDocument()
  expect(calls.some((url) => url.includes('/teleop/start'))).toBe(false)
})

test('calibration and pairing both use workflow preflight', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'real', hardware_motion_enabled: true, status: 'degraded', resources: {} })
    if (url.includes('/calibration/preflight') || url.includes('/pairing/preflight')) return jsonResponse({
      ready: false, simulation: false, workflow: url.includes('/pairing/') ? 'pairing' : 'calibration', mode: 'real',
      inventory: { mock: false, can: [], leaders: [], cameras: [] },
      issues: [{ code: 'leader_port_missing', resource: 'leader_left', title: 'Leader 串口不可用', message: '未发现端口。', action: '检查 USB。', severity: 'blocking' }],
    })
    if (url.includes('/calibration/status')) return jsonResponse({ leader_id: 'a1z_left_leader', exists: true, path: '/tmp/calibration.json' })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/tasks')) return jsonResponse([])
    return jsonResponse({})
  }))
  const user = userEvent.setup()
  const rendered = render(<App initialPath="/calibration" disableRealtime />)
  await user.click(await screen.findByRole('button', { name: '重新校准' }))
  expect(await screen.findByText('Leader 串口不可用')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '关闭' }))
  await user.click(screen.getByRole('checkbox', { name: /同一安全姿态已确认/ }))
  await user.click(screen.getByRole('button', { name: /读取 6D/ }))
  expect(await screen.findByText('Leader 串口不可用')).toBeInTheDocument()
  expect(calls.some((url) => url.includes('/calibration/preflight'))).toBe(true)
  expect(calls.some((url) => url.includes('/pairing/preflight'))).toBe(true)
  expect(calls.some((url) => url.includes('/calibration/start') || url.includes('/pairing/read'))).toBe(false)
  rendered.unmount()
})

test('recording and inference start paths use preflight before task creation', async () => {
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes('/system/health')) return jsonResponse({ mode: 'real', hardware_motion_enabled: true, status: 'degraded', resources: {} })
    if (url.includes('/record/compatibility')) return jsonResponse({ compatible: true, new_dataset: true, existing_episodes: 0, checks: { new_dataset: true } })
    if (url.includes('/inference/inspect-policy')) return jsonResponse({ policy_path: 'outputs/model', policy_type: 'act', state_dim: 14, action_dim: 14, camera_keys: ['top_rgb', 'left_wrist_rgb', 'right_wrist_rgb'], image_shape: [3, 480, 640], fps: 30, processor: 'normalizer', device: 'cuda', checks: { state: true }, compatible: true, compatibility_token: 'token', hardware_connected: false, mock: false })
    if (url.includes('/record/preflight') || url.includes('/inference/preflight')) return jsonResponse({
      ready: false, simulation: false, workflow: url.includes('/record/') ? 'recording' : 'inference', mode: 'real',
      inventory: { mock: false, can: [], leaders: [], cameras: [] },
      issues: [{ code: 'can_missing', resource: 'can0', title: 'can0 不存在', message: '未发现 CAN。', action: '初始化 can0。', severity: 'blocking' }],
    })
    if (url.includes('/calibration/profiles')) return jsonResponse({ items: [] })
    if (url.includes('/tasks')) return jsonResponse([])
    return jsonResponse({})
  }))
  const user = userEvent.setup()
  const recording = render(<App initialPath="/recording" disableRealtime />)
  await user.click(await screen.findByRole('button', { name: '检查 Dataset Compatibility' }))
  await screen.findByText(/COMPATIBLE/)
  await user.click(screen.getByRole('checkbox', { name: '确认录制安全检查' }))
  await user.click(screen.getByRole('button', { name: '开始录制任务' }))
  expect(await screen.findByText('can0 不存在')).toBeInTheDocument()
  recording.unmount()
  cleanup()

  const inference = render(<App initialPath="/inference" disableRealtime />)
  await user.click(await screen.findByRole('button', { name: /连接硬件之前检查 Policy/ }))
  await screen.findByText('Compatible')
  await user.click(screen.getByRole('checkbox', { name: /确认推理安全检查/ }))
  await user.click(screen.getByRole('button', { name: '开始安全推理' }))
  expect(await screen.findByText('can0 不存在')).toBeInTheDocument()
  expect(calls.some((url) => url.includes('/record/preflight'))).toBe(true)
  expect(calls.some((url) => url.includes('/inference/preflight'))).toBe(true)
  expect(calls.some((url) => url.includes('/record/start') || url.includes('/inference/start'))).toBe(false)
  inference.unmount()
})
