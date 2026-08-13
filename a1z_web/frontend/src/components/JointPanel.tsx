import { GlassCard, StatusDot } from './ui'

export function JointPanel({ title, health = 'unknown' }: { title: string; health?: string }) {
  return <GlassCard className="joint-panel">
    <header><div><span className="eyebrow">FOLLOWER</span><h3>{title}</h3></div><StatusDot state={health} label={health === 'unknown' ? 'N/A' : health} /></header>
    <div className="joint-grid">
      {[1, 2, 3, 4, 5, 6].map((joint) => <div key={joint}><span>J{joint}</span><strong>—</strong><small>rad</small></div>)}
      <div><span>Gripper</span><strong>—</strong><small>rad</small></div>
    </div>
    <p className="muted">仅显示工作进程上报的真实状态；当前无遥测时保持 N/A。</p>
  </GlassCard>
}
