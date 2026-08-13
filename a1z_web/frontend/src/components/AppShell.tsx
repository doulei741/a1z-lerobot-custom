import { useMutation, useQuery } from '@tanstack/react-query'
import { Bot, CircleGauge, Database, FileTerminal, Hand, OctagonX, SlidersHorizontal } from 'lucide-react'
import type { PropsWithChildren } from 'react'
import { useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import { LogDrawer } from './LogDrawer'
import { Button, StatusDot } from './ui'

const navigation = [
  { to: '/calibration', label: '机械臂校准', icon: SlidersHorizontal },
  { to: '/teleoperation', label: '遥控操作', icon: Hand },
  { to: '/recording', label: '数据录制', icon: Database },
  { to: '/inference', label: '模型推理', icon: CircleGauge },
]

export function AppShell({ children }: PropsWithChildren) {
  const activeTaskId = usePlatformStore((state) => state.activeTaskId)
  const setActiveTask = usePlatformStore((state) => state.setActiveTask)
  const setLogs = usePlatformStore((state) => state.setLogDrawer)
  const ws = usePlatformStore((state) => state.websocketState)
  const health = useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 5000 })
  const task = useQuery({ queryKey: ['task', activeTaskId], queryFn: () => api.task(activeTaskId!), enabled: Boolean(activeTaskId), refetchInterval: 1000 })
  const stop = useMutation({ mutationFn: () => api.stop(activeTaskId!), onSuccess: (result) => { if (['stopped', 'completed', 'failed', 'faulted'].includes(result.status)) setActiveTask(null) } })
  useEffect(() => {
    if (task.data && ['completed', 'stopped'].includes(task.data.status)) {
      const timer = window.setTimeout(() => setActiveTask(null), 1200)
      return () => window.clearTimeout(timer)
    }
  }, [setActiveTask, task.data])
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
        <Button variant="danger" disabled={!activeTaskId || stop.isPending} onClick={() => stop.mutate()}><OctagonX size={17} />软件停止</Button>
      </header>
      <main>{children}</main>
      <footer><span>软件停止 ≠ 硬件急停</span><span>现场必须保持物理急停 / 断能装置可用</span></footer>
    </div>
    <LogDrawer />
  </div>
}
