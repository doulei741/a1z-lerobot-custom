import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { RerunPreview } from '../components/RerunPreview'

afterEach(cleanup)

test('embeds the task-scoped Rerun viewer and offers a pop-out link', () => {
  render(<RerunPreview
    task={{
      task_id: 'teleop-1', task_type: 'teleoperation', status: 'ready', phase: 'running', pid: 12,
      start_time: '2026-08-14T00:00:00Z', end_time: null, health: {}, message: null, mock: false,
      metadata: { rerun: { enabled: true, web_port: 19090, grpc_port: 19876, url: 'http://127.0.0.1:19090', grpc_url: 'rerun+http://127.0.0.1:19876/proxy', cameras: ['top_rgb'] } },
    }}
    cameraNames={['top_rgb']}
  />)

  const source = screen.getByTitle('Rerun 实时相机画面').getAttribute('src')!
  expect(new URL(source).port).toBe('19090')
  expect(new URL(source).searchParams.get('url')).toBe('rerun+http://localhost:19876/proxy')
  expect(screen.getByRole('link', { name: '在新窗口打开 Rerun' })).toHaveAttribute('href', source)
})


test('does not pretend that mock mode has a real camera stream', () => {
  render(<RerunPreview
    task={{
      task_id: 'mock-1', task_type: 'teleoperation', status: 'ready', phase: 'ready', pid: null,
      start_time: '2026-08-14T00:00:00Z', end_time: null, health: {}, message: null, mock: true,
    }}
    cameraNames={['top_rgb']}
  />)

  expect(screen.getByText(/MOCK 模式不会读取真实相机/)).toBeInTheDocument()
  expect(screen.queryByTitle('Rerun 实时相机画面')).not.toBeInTheDocument()
})


test('explains that preview starts with the camera workflow', () => {
  render(<RerunPreview task={undefined} cameraNames={['top_rgb', 'left_wrist_rgb']} />)

  expect(screen.getByText(/启动任务后在此显示/)).toBeInTheDocument()
})
