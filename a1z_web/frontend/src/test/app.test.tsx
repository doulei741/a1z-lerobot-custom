import { cleanup, render, screen } from '@testing-library/react'
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
