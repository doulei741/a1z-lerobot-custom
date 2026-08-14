import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'

const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function installFetch(captured: Array<Record<string, unknown>>, existingEpisodes = 0) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/system/health')) return json({ mode: 'real', hardware_motion_enabled: true, status: 'healthy', resources: {} })
    if (url.includes('/devices')) return json({ mock: false, usb_can: [], can: [{ name: 'can0', state: 'healthy', bitrate: 1_000_000 }, { name: 'can1', state: 'healthy', bitrate: 1_000_000 }], leaders: [{ port: '/dev/ttyACM0', state: 'available' }, { port: '/dev/ttyACM1', state: 'available' }], cameras: [{ name: 'D435', serial: 'TOP' }, { name: 'D405', serial: 'LEFT' }, { name: 'D405', serial: 'RIGHT' }] })
    if (url.includes('/calibration/profiles')) return json({ items: [] })
    if (url.includes('/tasks')) return json([])
    if (url.includes('/record/compatibility')) return json({ compatible: true, new_dataset: existingEpisodes === 0, existing_episodes: existingEpisodes, checks: { state: true, action: true, fps: true, camera_keys: true, resolution: true } })
    if (url.includes('/inference/inspect-policy')) return json({ policy_path: 'outputs/model', policy_type: 'act', state_dim: 14, action_dim: 14, camera_keys: ['top_rgb', 'left_wrist_rgb', 'right_wrist_rgb'], image_shape: [3, 480, 640], fps: 30, processor: 'normalizer', device: 'cuda', checks: { state: true }, compatible: true, compatibility_token: 'token', hardware_connected: false, mock: false })
    if (url.includes('/preflight')) {
      captured.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
      return json({ ready: false, simulation: false, workflow: 'teleoperation', mode: 'real', issues: [{ code: 'test', resource: 'test', title: 'captured', message: 'captured', action: 'close', severity: 'blocking' }], inventory: { mock: false, usb_can: [], can: [], leaders: [], cameras: [] } })
    }
    return json({})
  }))
}

test('teleoperation sends graphical CAN, leader, camera and safety parameters', async () => {
  const captured: Array<Record<string, unknown>> = []
  installFetch(captured)
  const user = userEvent.setup()
  render(<App initialPath="/teleoperation" disableRealtime />)

  await user.clear(await screen.findByLabelText('Left Leader ID'))
  await user.type(screen.getByLabelText('Left Leader ID'), 'left_custom')
  await user.selectOptions(screen.getByLabelText('Camera'), 'configured')
  await user.clear(screen.getByLabelText('Camera Width'))
  await user.type(screen.getByLabelText('Camera Width'), '848')
  await user.click(screen.getByRole('checkbox', { name: /确认运动安全检查/ }))
  await user.click(screen.getByRole('button', { name: 'Start Teleoperation' }))

  const payload = captured.at(0)!
  expect(payload.left_leader_id).toBe('left_custom')
  expect(payload.left_can).toBe('can0')
  expect((payload.cameras as Record<string, { width: number }>).top_rgb!.width).toBe(848)
})

test('teleoperation exposes absolute gripper, compressed display and optional duration', async () => {
  const captured: Array<Record<string, unknown>> = []
  installFetch(captured)
  const user = userEvent.setup()
  render(<App initialPath="/teleoperation" disableRealtime />)

  expect(await screen.findByRole('checkbox', { name: 'Gripper start hold' })).not.toBeChecked()
  await user.click(screen.getByRole('checkbox', { name: 'Rerun display_data' }))
  await user.click(screen.getByRole('checkbox', { name: 'Display compressed images' }))
  await user.type(screen.getByLabelText('Teleoperation duration'), '12')
  await user.click(screen.getByRole('checkbox', { name: /确认运动安全检查/ }))
  await user.click(screen.getByRole('button', { name: 'Start Teleoperation' }))

  const payload = captured.at(0)!
  expect(payload.gripper_start_hold).toBe(false)
  expect(payload.display_compressed_images).toBe(true)
  expect(payload.teleop_time_s).toBe(12)
})

test('recording exposes timing, control, camera and disconnect parameters', async () => {
  const captured: Array<Record<string, unknown>> = []
  installFetch(captured)
  const user = userEvent.setup()
  render(<App initialPath="/recording" disableRealtime />)

  await user.clear(await screen.findByLabelText('Episode Time'))
  await user.type(screen.getByLabelText('Episode Time'), '45')
  await user.clear(screen.getByLabelText('Max joint delta'))
  await user.type(screen.getByLabelText('Max joint delta'), '0.02')
  await user.click(screen.getByLabelText('Display compressed images'))
  await user.click(screen.getByRole('button', { name: '检查 Dataset Compatibility' }))
  await screen.findByText(/COMPATIBLE/)
  await user.click(screen.getByLabelText('确认录制安全检查'))
  await user.click(screen.getByRole('button', { name: '开始录制任务' }))

  const payload = captured.at(0)!
  expect((payload.dataset as Record<string, unknown>).episode_time_s).toBe(45)
  expect(payload.max_joint_delta).toBe(0.02)
  expect(payload.display_compressed_images).toBe(true)
})

test('recording resume derives additions from existing and target episode totals', async () => {
  const captured: Array<Record<string, unknown>> = []
  installFetch(captured, 25)
  const user = userEvent.setup()
  render(<App initialPath="/recording" disableRealtime />)

  await user.click(await screen.findByRole('checkbox', { name: /Resume 现有数据集/ }))
  await user.click(screen.getByRole('button', { name: '检查 Dataset Compatibility' }))
  expect(await screen.findByText(/Existing Episodes: 25/)).toBeInTheDocument()
  const target = screen.getByLabelText('目标总 Episode')
  await user.clear(target)
  await user.type(target, '45')
  await user.click(screen.getByLabelText('Streaming Encoding'))
  await user.clear(screen.getByLabelText('Writer Threads / Camera'))
  await user.type(screen.getByLabelText('Writer Threads / Camera'), '6')
  await user.clear(screen.getByLabelText('Encoder CRF'))
  await user.type(screen.getByLabelText('Encoder CRF'), '26')
  await user.click(screen.getByLabelText('确认录制安全检查'))
  await user.click(screen.getByRole('button', { name: '开始录制任务' }))

  const payload = captured.at(0)!
  expect(payload.resume).toBe(true)
  expect(payload.gripper_start_hold).toBe(false)
  expect((payload.dataset as Record<string, unknown>).num_episodes).toBe(20)
  expect((payload.dataset as Record<string, unknown>).streaming_encoding).toBe(true)
  expect((payload.dataset as Record<string, unknown>).num_image_writer_threads_per_camera).toBe(6)
  expect(((payload.dataset as Record<string, unknown>).camera_encoder as Record<string, unknown>).crf).toBe(26)
})

test('inference exposes CAN, task, FPS, EMA and camera parameters', async () => {
  const captured: Array<Record<string, unknown>> = []
  installFetch(captured)
  const user = userEvent.setup()
  render(<App initialPath="/inference" disableRealtime />)

  await user.click(await screen.findByRole('button', { name: /连接硬件之前检查 Policy/ }))
  await screen.findByText('Compatible')
  await user.clear(screen.getByLabelText('Task instruction'))
  await user.type(screen.getByLabelText('Task instruction'), 'Insert pen')
  await user.clear(screen.getByLabelText('EMA alpha'))
  await user.type(screen.getByLabelText('EMA alpha'), '0.25')
  await user.click(screen.getByRole('checkbox', { name: /确认推理安全检查/ }))
  await user.click(screen.getByRole('button', { name: '开始安全推理' }))

  const payload = captured.at(0)!
  expect(payload.task).toBe('Insert pen')
  expect(payload.ema_alpha).toBe(0.25)
  expect(payload.right_can).toBe('can1')
})
