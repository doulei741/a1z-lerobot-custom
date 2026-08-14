import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { PreflightDialog } from '../components/PreflightDialog'
import type { PreflightReport } from '../types'

const blockingReport: PreflightReport = {
  ready: false,
  simulation: false,
  workflow: 'teleoperation',
  mode: 'real',
  inventory: { mock: false, can: [], leaders: [], cameras: [] },
  issues: [{
    code: 'can_missing',
    resource: 'can0',
    title: 'can0 不存在',
    message: 'Left Follower 需要 can0。',
    action: '运行 setup.sh can0 后重新检查。',
    severity: 'blocking',
  }],
}

afterEach(cleanup)

test('blocking preflight explains the issue and has no bypass action', () => {
  render(<PreflightDialog report={blockingReport} onClose={vi.fn()} onContinueSimulation={vi.fn()} />)

  expect(screen.getByRole('heading', { name: '设备检查未通过' })).toBeInTheDocument()
  expect(screen.getByText('can0 不存在')).toBeInTheDocument()
  expect(screen.getByText(/运行 setup\.sh can0 后重新检查/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '继续 Mock 仿真' })).not.toBeInTheDocument()
})

test('mock preflight requires explicit acknowledgement before simulation', async () => {
  const user = userEvent.setup()
  const continueSimulation = vi.fn()
  render(<PreflightDialog report={{
    ...blockingReport,
    ready: true,
    simulation: true,
    mode: 'mock',
    issues: [{
      code: 'mock_simulation',
      resource: 'web_mode',
      title: '当前是 Mock 仿真模式',
      message: '不会移动真实设备。',
      action: '切换 Real 模式后重启。',
      severity: 'warning',
    }],
  }} onClose={vi.fn()} onContinueSimulation={continueSimulation} />)

  expect(screen.getByRole('heading', { name: '当前运行在 Mock 仿真模式' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '继续 Mock 仿真' }))
  expect(continueSimulation).toHaveBeenCalledOnce()
})
