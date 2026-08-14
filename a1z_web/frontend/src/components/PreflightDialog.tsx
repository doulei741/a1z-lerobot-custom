import * as Dialog from '@radix-ui/react-dialog'
import { AlertTriangle, CheckCircle2, X } from 'lucide-react'
import type { PreflightReport } from '../types'
import { Button } from './ui'

export function PreflightDialog({
  report,
  onClose,
  onContinueSimulation,
}: {
  report: PreflightReport | null
  onClose: () => void
  onContinueSimulation: () => void
}) {
  if (!report) return null
  const simulation = report.simulation
  return <Dialog.Root open onOpenChange={(open) => { if (!open) onClose() }}>
    <Dialog.Portal>
      <Dialog.Overlay className="preflight-overlay" />
      <Dialog.Content className="preflight-dialog">
        <header>
          <div className={simulation ? 'preflight-icon warning' : 'preflight-icon fault'}>
            {simulation ? <AlertTriangle /> : <X />}
          </div>
          <div>
            <Dialog.Title>{simulation ? '当前运行在 Mock 仿真模式' : '设备检查未通过'}</Dialog.Title>
            <Dialog.Description>
              {simulation
                ? '可以继续验证页面和状态机，但真实机械臂不会连接或移动。'
                : '后端已阻止启动。请按下面的步骤修复后重新检查。'}
            </Dialog.Description>
          </div>
          <Dialog.Close aria-label="关闭设备检查"><X size={18} /></Dialog.Close>
        </header>
        <div className="preflight-issues">
          {report.issues.map((issue) => <article key={`${issue.code}-${issue.resource}`} className={`preflight-issue ${issue.severity}`}>
            <div>{issue.severity === 'warning' ? <AlertTriangle /> : <X />}</div>
            <div><strong>{issue.title}</strong><p>{issue.message}</p><span><CheckCircle2 />需要执行：{issue.action}</span></div>
          </article>)}
        </div>
        <footer>
          <Button variant="secondary" onClick={onClose}>关闭</Button>
          {simulation && <Button onClick={onContinueSimulation}>继续 Mock 仿真</Button>}
        </footer>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
}
