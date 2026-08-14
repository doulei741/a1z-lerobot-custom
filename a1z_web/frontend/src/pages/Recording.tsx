import { useMutation, useQuery } from '@tanstack/react-query'
import { FastForward, RotateCcw, Save, ShieldCheck, Square, Video } from 'lucide-react'
import { useState } from 'react'
import { Button, ErrorNotice, Field, GlassCard, PageTitle, Segmented, StatusDot } from '../components/ui'
import { PreflightDialog } from '../components/PreflightDialog'
import { usePreflightStart } from '../hooks/usePreflightStart'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'

const dualLeft = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.08975979] }
const dualRight = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975] }
const singleMapping = { signs: [-1, 1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.040418965, 1.567886653, -1.698370257, -0.144229406, -0.011507665, -0.016411362] }

export function Recording() {
  const [confirmed, setConfirmed] = useState(false)
  const [mode, setMode] = useState<'single' | 'dual'>('dual')
  const [repoId, setRepoId] = useState('local/a1z_dual_web')
  const [root, setRoot] = useState('datasets/a1z_dual_web')
  const [taskText, setTaskText] = useState('Coordinate both arms to complete the configured task')
  const [episodes, setEpisodes] = useState(15)
  const [resume, setResume] = useState(false)
  const [rightWristSerial, setRightWristSerial] = useState('260522278763')
  const [leftMapping, setLeftMapping] = useState(dualLeft)
  const [rightMapping, setRightMapping] = useState(dualRight)
  const setActive = usePlatformStore((state) => state.setActiveTask)
  const taskId = usePlatformStore((state) => state.activeTaskId)
  const task = useQuery({ queryKey: ['task', taskId], queryFn: () => api.task(taskId!), enabled: Boolean(taskId), refetchInterval: 200 })
  const profiles = useQuery({ queryKey: ['pairing-profiles'], queryFn: api.pairingProfiles })
  const requestBody = () => ({ mode, safety_confirmed: confirmed, resume, right_wrist_serial: rightWristSerial, left_mapping: leftMapping, right_mapping: rightMapping, dataset: { repo_id: repoId, root, single_task: taskText, num_episodes: episodes, episode_time_s: 60, reset_time_s: 10, fps: 30, video: true } })
  const compatibility = useMutation({ mutationFn: () => api.recordCompatibility(requestBody()) })
  const guardedStart = usePreflightStart(api.preflightRecord, api.startRecord, (result) => setActive(result.task_id, result.task_type))
  const command = useMutation({ mutationFn: (action: string) => api.recordAction(taskId!, action, crypto.randomUUID(), task.data?.episode_index ?? 0), onSuccess: () => void task.refetch() })
  const phase = task.data?.record_phase ?? 'idle'
  const existing = task.data?.existing_episodes ?? 0
  const isRecording = phase === 'recording'
  const busy = phase === 'saving' || phase === 'resetting'
  const cameraResources: Array<[string, string]> = mode === 'dual'
    ? [['Top RGB · D435', 'top_camera'], ['Left Wrist · D405', 'left_wrist_camera'], ['Right Wrist · D405', 'right_wrist_camera']]
    : [['Top RGB · D435', 'top_camera'], ['Wrist RGB · D405', 'left_wrist_camera']]
  return <div className="page">
    <PageTitle title="数据录制" description="显式 Episode 协议管理保存、重录、Reset 与 Quick Next，每个动作均受状态机约束。" />
    <div className="record-layout">
      <div className="record-main"><GlassCard className="record-status"><div className="card-heading"><div><span className="eyebrow">RECORD PROTOCOL</span><h2>Episode Session</h2></div><span className={`phase phase-${phase}`}>{phase.toUpperCase()}</span></div><div className="episode-stats"><div><span>Existing Episodes</span><strong>{existing}</strong></div><div><span>Add Episodes</span><strong>{task.data?.add_episodes ?? episodes}</strong></div><div><span>Total After Session</span><strong>{task.data?.total_after_session ?? existing + episodes}</strong></div><div><span>Current Frames</span><strong>{task.data?.frames ?? 0}</strong></div></div>{task.data?.fault_reason && <div className="notice notice-error"><b>FAULT</b>{task.data.fault_reason}<br />最后可信 Episode：{task.data.last_trusted_episode}；当前 Episode {task.data.current_episode_invalid ? '已作废' : '未作废'}。</div>}<div className="record-controls"><Button disabled={phase !== 'ready'} onClick={() => command.mutate('start-episode')}><Video size={16} />开始本轮 Episode</Button><Button variant="secondary" disabled={!isRecording || (task.data?.frames ?? 0) < 1 || command.isPending} onClick={() => command.mutate('finish-episode')}><Save size={16} />提前结束并保存</Button><Button variant="secondary" disabled={!isRecording || command.isPending} onClick={() => command.mutate('rerecord')}><RotateCcw size={16} />丢弃本轮并重录</Button><Button variant="secondary" disabled={!isRecording || (task.data?.frames ?? 0) < 1 || command.isPending} onClick={() => command.mutate('quick-next')}><FastForward size={16} />快速开始下一轮</Button>{phase === 'resetting' && <Button onClick={() => command.mutate('reset-done')}>重置完成</Button>}<Button variant="danger" disabled={!taskId || busy} onClick={() => api.stop(taskId!)}><Square size={15} />正常停止整个任务</Button>{task.data?.mock && <Button variant="secondary" disabled={!isRecording} onClick={() => api.mockFrame(taskId!)}>模拟一帧</Button>}</div><p className="muted">Quick Next：结束 → saving_complete → reset → health check → ready → 下一轮；不会跳过保存。</p></GlassCard>
        <div className="camera-grid">{cameraResources.map(([name, resource]) => <GlassCard className="camera-placeholder" key={name}><div><Video /><StatusDot state={task.data?.status === 'faulted' ? 'fault' : task.data?.health[resource] ?? 'unknown'} label="480p · 30 FPS" /></div><strong>{name}</strong><p>画面由任务进程发送至 Rerun；Web 不二次占用设备。</p></GlassCard>)}</div></div>
      <GlassCard className="record-config"><div className="card-heading"><div><span className="eyebrow">DATASET</span><h2>录制配置</h2></div></div><Segmented value={mode} onChange={(value) => { setMode(value); setLeftMapping(value === 'single' ? singleMapping : dualLeft); compatibility.reset() }} /><Field label="Repository ID"><input value={repoId} onChange={(event) => { setRepoId(event.target.value); compatibility.reset() }} /></Field><Field label="Dataset Root"><input value={root} onChange={(event) => { setRoot(event.target.value); compatibility.reset() }} /></Field>{mode === 'dual' && <Field label="Right D405 Serial"><input value={rightWristSerial} onChange={(event) => setRightWristSerial(event.target.value)} /></Field>}<Field label="Pairing Profiles"><select defaultValue="" onChange={(event) => { const profile = profiles.data?.items.find((item) => item.profile_id === event.target.value); if (!profile) return; const mapping = { signs: profile.signs, scales: profile.scales, offsets_rad: profile.offsets_rad }; if (profile.side === 'left') setLeftMapping(mapping); else setRightMapping(mapping); compatibility.reset() }}><option value="">现场验证默认值</option>{profiles.data?.items.filter((profile) => mode === 'dual' || profile.side === 'left').map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.profile_id} · {profile.side}</option>)}</select></Field><Field label="Task"><textarea rows={4} value={taskText} onChange={(event) => setTaskText(event.target.value)} /></Field><Field label="本次新增 Episode"><input type="number" min={1} value={episodes} onChange={(event) => setEpisodes(Number(event.target.value))} /></Field><div className="form-grid"><Field label="Episode Time"><input value="60 s" readOnly /></Field><Field label="Reset Time"><input value="10 s" readOnly /></Field></div><label className="toggle-line"><input type="checkbox" checked={resume} onChange={(event) => { setResume(event.target.checked); compatibility.reset() }} /><span>Resume 现有数据集（启动前执行完整契约检查）</span></label><Button variant="secondary" onClick={() => compatibility.mutate()} disabled={compatibility.isPending}>检查 Dataset Compatibility</Button>{compatibility.data && <div className={compatibility.data.compatible ? 'notice' : 'notice notice-error'}><b>{compatibility.data.compatible ? 'COMPATIBLE' : 'INCOMPATIBLE'}</b> Existing Episodes: {compatibility.data.existing_episodes}<br />{Object.entries(compatibility.data.checks).map(([key, value]) => `${key}: ${value ? '✓' : '✗'}`).join(' · ')}</div>}<label className="safety-check"><input aria-label="确认录制安全检查" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><ShieldCheck /><span><b>确认录制安全检查</b>相机、CAN、配对与物理急停已确认。</span></label><ErrorNotice error={(compatibility.error ?? guardedStart.error ?? command.error) as Error | null} /><Button disabled={!confirmed || !compatibility.data?.compatible || guardedStart.isPending || Boolean(taskId)} onClick={() => guardedStart.run(requestBody())}>开始录制任务</Button></GlassCard>
    </div>
    <PreflightDialog report={guardedStart.report} onClose={guardedStart.closeReport} onContinueSimulation={guardedStart.continueSimulation} />
  </div>
}
