import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'

const response = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
}))

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('device center discovers all product hardware and initializes missing CAN', async () => {
  let canReady = false
  const calls: string[] = []
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    calls.push(url)
    if (url.includes('/system/health')) return response({ mode: 'real', hardware_motion_enabled: true, status: 'degraded', resources: {} })
    if (url.includes('/devices/can/initialize')) { canReady = true; return response({ state: 'ready', simulation: false, interface: { name: 'can0', state: 'healthy', bitrate: 1_000_000 } }) }
    if (url.includes('/devices')) return response({
      mock: false,
      usb_can: [{ usb_path: '1-2.2', vendor_id: 'a8fa', product_id: '8598', serial: 'CAN-A', product: 'HHS CANFD Pro-II', supported: true }],
      can: canReady ? [{ name: 'can0', state: 'healthy', bitrate: 1_000_000 }] : [],
      leaders: [{ port: '/dev/ttyACM0', state: 'available' }, { port: '/dev/ttyACM1', state: 'available' }],
      cameras: [{ name: 'Intel RealSense D435', serial: 'TOP', state: 'available' }],
    })
    if (url.includes('/tasks')) return response([])
    if (url.includes('/calibration/status')) return response({ leader_id: 'a1z_left_leader', exists: false, path: '/tmp/no.json' })
    if (url.includes('/calibration/profiles')) return response({ items: [] })
    return response({})
  }))
  const user = userEvent.setup()
  render(<App initialPath="/calibration" disableRealtime />)

  await user.click(await screen.findByRole('button', { name: '设备中心' }))
  expect(await screen.findByRole('heading', { name: '设备准备中心' })).toBeInTheDocument()
  expect(screen.getByText('CAN-A')).toBeInTheDocument()
  expect(screen.getByText('/dev/ttyACM0')).toBeInTheDocument()
  expect(screen.getByText('TOP')).toBeInTheDocument()
  expect(screen.getByText('0 / 2 CAN Ready')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '初始化 can0' }))

  await waitFor(() => expect(calls.some((url) => url.includes('/devices/can/initialize'))).toBe(true))
  expect(await screen.findByText('can0 · 1 Mbps')).toBeInTheDocument()
})


test('device center labels Mock initialization and never presents it as real hardware', async () => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/system/health')) return response({ mode: 'mock', hardware_motion_enabled: false, status: 'healthy', resources: {} })
    if (url.includes('/devices')) return response({ mock: true, usb_can: [], can: [{ name: 'can0', state: 'healthy', bitrate: 1_000_000 }, { name: 'can1', state: 'healthy', bitrate: 1_000_000 }], leaders: [], cameras: [] })
    if (url.includes('/tasks')) return response([])
    if (url.includes('/calibration/status')) return response({ leader_id: 'a1z_left_leader', exists: false, path: '/tmp/no.json' })
    if (url.includes('/calibration/profiles')) return response({ items: [] })
    return response({})
  }))
  const user = userEvent.setup()
  render(<App initialPath="/calibration" disableRealtime />)

  await user.click(await screen.findByRole('button', { name: '设备中心' }))

  expect(await screen.findByText('Mock 设备清单')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /初始化 can/ })).not.toBeInTheDocument()
})
