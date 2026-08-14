import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { App } from '../app/App'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

test('operator can switch from mock to real only through the hardware safety confirmation', async () => {
  const requests: Array<{ url: string; body?: string }> = []
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input)
    requests.push({ url, body: init?.body as string | undefined })
    if (url.includes('/system/mode')) return Promise.resolve(new Response(JSON.stringify({ mode: 'real', hardware_motion_enabled: true }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (url.includes('/system/health')) return Promise.resolve(new Response(JSON.stringify({ mode: 'mock', hardware_motion_enabled: false, status: 'healthy', resources: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (url.includes('/calibration/profiles')) return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (url.includes('/calibration/status')) return Promise.resolve(new Response(JSON.stringify({ exists: false }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    if (url.includes('/tasks')) return Promise.resolve(new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    return Promise.resolve(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
  }))
  const user = userEvent.setup()

  render(<App initialPath="/calibration" disableRealtime />)
  await user.click(await screen.findByRole('button', { name: /Mock 仿真/ }))
  expect(screen.getByRole('heading', { name: '切换到真机实操' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '启用真机模式' })).toBeDisabled()
  await user.click(screen.getByRole('checkbox', { name: /工作区和物理急停/ }))
  await user.click(screen.getByRole('button', { name: '启用真机模式' }))

  const request = requests.find((item) => item.url.includes('/system/mode'))
  expect(JSON.parse(request!.body!)).toEqual({ mode: 'real', hardware_confirmation: true })
})
