import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, Bot, CircleGauge, Database, FileTerminal, Hand, OctagonX, SlidersHorizontal, Usb } from 'lucide-react'
import type { PropsWithChildren } from 'react'
import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import { LogDrawer } from './LogDrawer'
import { DeviceCenter } from './DeviceCenter'
import { PreflightDialog } from './PreflightDialog'
import { RuntimeModeControl } from './RuntimeModeControl'
import { Button, StatusDot } from './ui'
import type { PreflightReport } from '../types'

const navigation = [
  { to: '/calibration', label: '机械臂校准', icon: SlidersHorizontal },
  { to: '/teleoperation', label: '遥控操作', icon: Hand },
  { to: '/recording', label: '数据录制', icon: Database },
  { to: '/inference', label: '模型推理', icon: CircleGauge },
]

const ACTIVE_TASK_STATUSES = new Set(['created', 'starting', 'ready', 'running', 'stopping'])

export function AppShell({ children }: PropsWithChildren) {
  const activeTaskId = usePlatformStore((state) => state.activeTaskId)
  const activeTaskObserved = usePlatformStore((state) => state.activeTaskObserved)
  const setActiveTask = usePlatformStore((state) => state.setActiveTask)
  const adoptActiveTask = usePlatformStore((state) => state.adoptActiveTask)
  const setLogs = usePlatformStore((state) => state.setLogDrawer)
  const ws = usePlatformStore((state) => state.websocketState)
  const [dismissedFault, setDismissedFault] = useState<string | null>(null)
  const [deviceCenterOpen, setDeviceCenterOpen] = useState(false)
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 })
  const task = useQuery({
    queryKey: ['task', activeTaskId],
    queryFn: () => api.task(activeTaskId!),
    enabled: Boolean(activeTaskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return !status || ACTIVE_TASK_STATUSES.has(status) ? 2000 : false
    },
  })
  const stop = useMutation({ mutationFn: () => api.stop(activeTaskId!), onSuccess: (result) => { if (['stopped', 'completed', 'failed', 'faulted'].includes(result.status)) setActiveTask(null) } })
  useEffect(() => {
    if (!task.data || task.data.task_id !== activeTaskId) return
    if (ACTIVE_TASK_STATUSES.has(task.data.status)) {
      if (!activeTaskObserved) adoptActiveTask()
      return
    }
    if (['failed', 'faulted'].includes(task.data.status) && !activeTaskObserved) {
      setActiveTask(null)
      return
    }
    if (['completed', 'stopped'].includes(task.data.status)) {
      const timer = window.setTimeout(() => setActiveTask(null), 1200)
      return () => window.clearTimeout(timer)
    }
  }, [activeTaskId, activeTaskObserved, adoptActiveTask, setActiveTask, task.data])
  const faultReport: PreflightReport | null = activeTaskObserved && task.data && ['failed', 'faulted'].includes(task.data.status) && dismissedFault !== task.data.task_id ? {
    ready: false,
    simulation: false,
    workflow: task.data.task_type === 'pairing' ? 'pairing' : task.data.task_type,
    mode: task.data.mock ? 'mock' : 'real',
    inventory: { mock: task.data.mock, can: [], leaders: [], cameras: [] },
    issues: [{
      code: 'task_fault', resource: task.data.task_id, title: '任务启动或运行失败',
      message: task.data.message ?? `任务状态为 ${task.data.status}，控制进程已停止。`,
      action: '打开右侧“日志”，查看最后的 ERROR/WARN；修复设备或配置后重新执行启动前检查。',
      severity: 'blocking',
    }],
  } : null
  const dismissFault = () => {
    const failedTaskId = task.data?.task_id ?? null
    setDismissedFault(failedTaskId)
    if (failedTaskId && ['failed', 'faulted'].includes(task.data?.status ?? '')) {
      setActiveTask(null)
    }
  }
  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><Bot /></div><div><strong>A1Z LeRobot</strong><span>Control Platform</span></div></div>
      <nav>{navigation.map(({ to, label, icon: Icon }) => <NavLink to={to} key={to}><Icon size={19} /><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-bottom"><button onClick={() => setLogs(true)}><FileTerminal size={18} />日志</button></div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <div className="system-state"><StatusDot state={health.data?.status ?? 'unknown'} label="系统" /><StatusDot state={ws === 'connected' ? 'healthy' : ws === 'connecting' ? 'degraded' : 'unknown'} label="实时通道" />{health.data?.mode === 'mock' && <span className="mock-badge">MOCK</span>}</div>
        <div className="active-task">{task.data ? <><span>{task.data.task_type}</span><strong>{task.data.status.toUpperCase()}</strong><code>{task.data.task_id}</code></> : <span>无活动任务</span>}</div>
        <div className="topbar-actions">{health.data && <RuntimeModeControl mode={health.data.mode} activeTask={Boolean(activeTaskId && (!task.data || ACTIVE_TASK_STATUSES.has(task.data.status)))} />}<Button variant="secondary" onClick={() => setDeviceCenterOpen(true)}><Usb size={16} />设备中心</Button><Button variant="danger" disabled={!activeTaskId || Boolean(task.data && !ACTIVE_TASK_STATUSES.has(task.data.status)) || stop.isPending} onClick={() => stop.mutate()}><OctagonX size={17} />软件停止</Button></div>
      </header>
      {health.data?.mode === 'mock' && <div className="mode-banner"><AlertTriangle size={16} /><strong>Mock 仿真模式</strong><span>页面不会连接或移动真实机械臂；启动动作前会再次提示。</span></div>}
      {health.data?.mode === 'real' && !health.data.hardware_motion_enabled && <div className="mode-banner"><AlertTriangle size={16} /><strong>实机动作已禁用</strong><span>设置 A1Z_WEB_ALLOW_HARDWARE=1 并重启后端后才能启动机器人任务。</span></div>}
      <main>{children}</main>
      <footer><span>软件停止 ≠ 硬件急停</span><span>现场必须保持物理急停 / 断能装置可用</span></footer>
    </div>
    <LogDrawer />
    <DeviceCenter open={deviceCenterOpen} onOpenChange={setDeviceCenterOpen} />
    <PreflightDialog report={faultReport} onClose={dismissFault} onContinueSimulation={dismissFault} />
  </div>
}
