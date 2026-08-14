import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'

const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

function installFetch(captured: Array<Record<string, unknown>>) {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    if (url.includes('/system/health')) return json({ mode: 'real', hardware_motion_enabled: true, status: 'healthy', resources: {} })
    if (url.includes('/devices')) return json({ mock: false, usb_can: [], can: [{ name: 'can0', state: 'healthy', bitrate: 1_000_000 }, { name: 'can1', state: 'healthy', bitrate: 1_000_000 }], leaders: [{ port: '/dev/ttyACM0', state: 'available' }, { port: '/dev/ttyACM1', state: 'available' }], cameras: [{ name: 'D435', serial: 'TOP' }, { name: 'D405', serial: 'LEFT' }, { name: 'D405', serial: 'RIGHT' }] })
    if (url.includes('/calibration/profiles')) return json({ items: [] })
    if (url.includes('/tasks')) return json([])
    if (url.includes('/record/compatibility')) return json({ compatible: true, new_dataset: true, existing_episodes: 0, checks: { new_dataset: true } })
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
