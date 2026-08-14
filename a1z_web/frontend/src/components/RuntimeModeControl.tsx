import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Cpu, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { api } from '../services/api'
import type { SystemHealth } from '../types'
import { Button, ErrorNotice } from './ui'

interface RuntimeModeControlProps {
  mode: 'mock' | 'real'
  activeTask: boolean
}

export function RuntimeModeControl({ mode, activeTask }: RuntimeModeControlProps) {
  const [open, setOpen] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const client = useQueryClient()
  const target = mode === 'mock' ? 'real' : 'mock'
  const changeMode = useMutation({
    mutationFn: () => api.setRuntimeMode(target, target === 'real' && confirmed),
    onSuccess: (result) => {
      client.setQueryData<SystemHealth>(['health'], (current) => ({
        mode: result.mode,
        hardware_motion_enabled: result.hardware_motion_enabled,
        status: current?.status ?? 'unknown',
        resources: current?.resources ?? {},
      }))
      void client.invalidateQueries({ queryKey: ['devices'] })
      setOpen(false)
      setConfirmed(false)
    },
  })
  return <Dialog.Root open={open} onOpenChange={(value) => { setOpen(value); if (!value) setConfirmed(false) }}>
    <Dialog.Trigger asChild><Button variant="secondary" disabled={activeTask}><Cpu size={15} />{mode === 'mock' ? 'Mock 仿真' : '真机实操'}</Button></Dialog.Trigger>
    <Dialog.Portal><Dialog.Overlay className="preflight-overlay" /><Dialog.Content className="preflight-dialog runtime-mode-dialog">
      <header><div className={`preflight-icon ${target === 'real' ? 'fault' : 'warning'}`}>{target === 'real' ? <AlertTriangle /> : <Cpu />}</div><div><Dialog.Title>{target === 'real' ? '切换到真机实操' : '切换到 Mock 仿真'}</Dialog.Title><Dialog.Description>{target === 'real' ? '切换后，校准、遥控、录制和推理将允许连接真实硬件。' : '切换后新任务只模拟状态，不连接或移动真实硬件。'}</Dialog.Description></div><Dialog.Close aria-label="关闭模式切换"><X /></Dialog.Close></header>
      {target === 'real' ? <><div className="notice notice-error"><b>真机模式会允许机械臂运动</b>模式切换本身不会立即驱动电机；实际运动仍需各页面的 Preflight 和安全确认。</div><label className="safety-check"><input aria-label="确认工作区和物理急停" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><ShieldCheck /><span><b>确认工作区和物理急停</b>工作区已清空，CAN/Leader 映射明确，物理急停或断能装置随时可用。</span></label></> : <div className="notice"><b>安全降级</b>仅影响后续新任务；活动任务存在时后端禁止切换模式。</div>}
      <ErrorNotice error={changeMode.error as Error | null} />
      <footer><Dialog.Close asChild><Button variant="secondary">取消</Button></Dialog.Close><Button variant={target === 'real' ? 'danger' : 'primary'} disabled={changeMode.isPending || (target === 'real' && !confirmed)} onClick={() => changeMode.mutate()}>{target === 'real' ? '启用真机模式' : '切换到 Mock'}</Button></footer>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>
}
