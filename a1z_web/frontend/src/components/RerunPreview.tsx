import { Camera, ExternalLink } from 'lucide-react'
import type { RerunRuntime, TaskInfo } from '../types'
import { GlassCard } from './ui'

const TERMINAL = new Set(['completed', 'failed', 'faulted', 'stopped'])

function viewerUrl(runtime: RerunRuntime) {
  const resolved = new URL(runtime.url!)
  // The backend records a loopback-safe URL. Reuse the browser's hostname so
  // a laptop on the same LAN can open the same task-scoped viewer.
  const hostname = window.location.hostname || '127.0.0.1'
  resolved.hostname = hostname
  const connection = new URL(
    runtime.grpc_url ?? `rerun+http://127.0.0.1:${runtime.grpc_port}/proxy`,
  )
  connection.hostname = hostname
  // serve_web_viewer's connect_to option only affects the URL it opens itself.
  // An iframe must explicitly pass the gRPC recording source to the viewer.
  resolved.searchParams.set('url', connection.toString())
  return resolved.toString()
}

export function RerunPreview({ task, cameraNames }: { task?: TaskInfo; cameraNames: string[] }) {
  const runtime = task?.metadata?.rerun
  const cameras = runtime?.cameras.length ? runtime.cameras : cameraNames
  const canDisplay = Boolean(
    task && !task.mock && runtime?.enabled && runtime.url &&
    ['ready', 'running'].includes(task.status) && !TERMINAL.has(task.status),
  )
  const url = canDisplay ? viewerUrl(runtime!) : null

  return <GlassCard className="rerun-preview">
    <header>
      <div><span className="eyebrow">LIVE OBSERVATION</span><h2>Rerun 相机画面</h2></div>
      {url && <a className="rerun-popout" href={url} target="_blank" rel="noreferrer"><ExternalLink size={14} />在新窗口打开 Rerun</a>}
    </header>
    <div className="camera-tags">{cameras.map((name) => <span key={name}><Camera size={12} />{name}</span>)}</div>
    {url
      ? <iframe title="Rerun 实时相机画面" src={url} allow="clipboard-write; fullscreen" />
      : <div className="rerun-empty"><Camera size={28} />
        {task?.mock
          ? <><strong>MOCK CAMERA</strong><p>MOCK 模式不会读取真实相机，也不会显示伪造画面。</p></>
          : task?.status === 'starting'
            ? <><strong>正在准备 Rerun</strong><p>等待相机与机械臂完成 ready 握手。</p></>
            : task && TERMINAL.has(task.status)
              ? <><strong>预览已结束</strong><p>任务终止后 Rerun 服务随任务进程关闭。</p></>
              : <><strong>等待相机任务</strong><p>选择并启用相机，启动任务后在此显示同一份 Rerun 观测。</p></>}
      </div>}
    <p className="rerun-safety-note">画面来自当前 LeRobot 任务；Web 后端不会再次打开 RealSense。预览异常不会绕过任务安全状态。</p>
  </GlassCard>
}
