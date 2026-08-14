import { cleanup, render, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'
import { shouldInvalidateTask } from '../hooks/useRealtime'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

test('high-volume log events do not refetch task metadata', () => {
  expect(shouldInvalidateTask('log')).toBe(false)
  expect(shouldInvalidateTask('task')).toBe(true)
  expect(shouldInvalidateTask('fault')).toBe(true)
  expect(shouldInvalidateTask('record_phase')).toBe(true)
})

test('React StrictMode creates only one live WebSocket connection', async () => {
  const sockets: FakeWebSocket[] = []
  class FakeWebSocket {
    onopen: (() => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null
    onclose: (() => void) | null = null
    constructor() { sockets.push(this) }
    close() { this.onclose?.() }
  }
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const body = url.includes('/system/health')
      ? { mode: 'mock', hardware_motion_enabled: false, status: 'healthy', resources: {} }
      : url.includes('/devices')
        ? { mock: true, can: [], leaders: [], cameras: [] }
        : url.includes('/calibration/profiles')
          ? { items: [] }
          : { leader_id: 'a1z_left_leader', exists: false, path: '' }
    return Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }))

  render(<StrictMode><App initialPath="/calibration" /></StrictMode>)

  await waitFor(() => expect(sockets).toHaveLength(1))
})

test('multiple app roots in one browser document share one live WebSocket', async () => {
  const sockets: FakeWebSocket[] = []
  class FakeWebSocket {
    onopen: (() => void) | null = null
    onmessage: ((event: MessageEvent) => void) | null = null
    onclose: (() => void) | null = null
    constructor() { sockets.push(this) }
    close() { this.onclose?.() }
  }
  vi.stubGlobal('WebSocket', FakeWebSocket)
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('{}', {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  }))))

  const first = render(<App initialPath="/calibration" />)
  const second = render(<App initialPath="/calibration" />)

  await waitFor(() => expect(sockets).toHaveLength(1))
  first.unmount()
  expect(sockets).toHaveLength(1)
  second.unmount()
})
