import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, Cpu, FileCheck2, Play, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { JointPanel } from '../components/JointPanel'
import { PreflightDialog } from '../components/PreflightDialog'
import { Button, ErrorNotice, Field, GlassCard, PageTitle, Segmented, StatusDot } from '../components/ui'
import { usePreflightStart } from '../hooks/usePreflightStart'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import type { PolicyReport } from '../types'

export function Inference() {
  const [mode, setMode] = useState<'single' | 'dual'>('dual')
  const [policyPath, setPolicyPath] = useState('outputs/a1z_dual_task_8.11/checkpoints/last/pretrained_model')
  const [report, setReport] = useState<PolicyReport | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [duration, setDuration] = useState(10)
  const [preset, setPreset] = useState<'safe' | 'normal' | 'custom'>('safe')
  const [delta, setDelta] = useState(0.01)
  const [inferenceType, setInferenceType] = useState<'sync' | 'async'>('sync')
  const [displayData, setDisplayData] = useState(true)
  const [returnHome, setReturnHome] = useState(false)
  const [openGrippers, setOpenGrippers] = useState(false)
  const [topSerial, setTopSerial] = useState('025222071608')
  const [leftSerial, setLeftSerial] = useState('260522273365')
  const [rightSerial, setRightSerial] = useState('260522278763')
  const [leftCan, setLeftCan] = useState<'can0' | 'can1'>('can0')
  const [rightCan, setRightCan] = useState<'can0' | 'can1'>('can1')
  const [fps, setFps] = useState(30)
  const [ema, setEma] = useState(0.3)
  const [taskInstruction, setTaskInstruction] = useState('Execute the trained task')
  const [cameraWidth, setCameraWidth] = useState(640)
  const [cameraHeight, setCameraHeight] = useState(480)
  const setActive = usePlatformStore((state) => state.setActiveTask)
  const taskId = usePlatformStore((state) => state.activeTaskId)
  const task = useQuery({ queryKey: ['task', taskId], queryFn: () => api.task(taskId!), enabled: Boolean(taskId) })
  const devices = useQuery({ queryKey: ['devices'], queryFn: api.devices })
  const inspect = useMutation({ mutationFn: () => api.inspectPolicy(policyPath, mode), onSuccess: setReport })
  const camera = (serial: string) => ({ serial, width: cameraWidth, height: cameraHeight, fps, use_depth: false })
  const requestBody = () => ({ mode, policy_path: policyPath, compatibility_token: report?.compatibility_token, safety_confirmed: confirmed, duration, fps, ema_alpha: ema, max_joint_delta: delta, inference_type: inferenceType, strategy_type: 'base', task: taskInstruction, left_can: leftCan, right_can: rightCan, display_data: displayData, return_home_on_disconnect: returnHome, open_grippers_on_disconnect: openGrippers, gripper_start_hold: false, cameras: mode === 'dual' ? { top_rgb: camera(topSerial), left_wrist_rgb: camera(leftSerial), right_wrist_rgb: camera(rightSerial) } : { top_rgb: camera(topSerial), wrist_rgb: camera(leftSerial) } })
  const guardedStart = usePreflightStart(api.preflightInference, api.startInference, (result) => setActive(result.task_id, result.task_type))
  const choosePreset = (value: typeof preset) => { setPreset(value); if (value === 'safe') { setDelta(0.01); setDuration(10); setInferenceType('sync') } else if (value === 'normal') { setDelta(0.05); setDuration(60); setInferenceType('sync') } }
  return <div className="page">
    <PageTitle title="模型推理" description="ACT Policy First、Hardware Last：模型、处理器和特征契约全部通过后才允许连接机械臂。" />
    <div className="inference-layout"><div className="inference-main"><GlassCard><div className="card-heading"><div><span className="eyebrow">POLICY INSPECTION</span><h2>Inference Compatibility</h2></div><StatusDot state={report?.compatible ? 'healthy' : report ? 'fault' : 'unknown'} label={report?.compatible ? 'Compatible' : 'Not inspected'} /></div><Segmented value={mode} onChange={(value) => { setMode(value); setReport(null) }} /><Field label="Checkpoint Path" hint="项目内目录；先仅读取 config / processor，不连接硬件"><input value={policyPath} onChange={(event) => { setPolicyPath(event.target.value); setReport(null) }} /></Field><Button variant="secondary" onClick={() => inspect.mutate()} disabled={inspect.isPending}><FileCheck2 size={16} />连接硬件之前检查 Policy</Button><ErrorNotice error={inspect.error as Error | null} />{report && <div className="compatibility"><div className="policy-meta"><div><span>Policy</span><b>{report.policy_type}</b></div><div><span>State</span><b>{report.state_dim}D</b></div><div><span>Action</span><b>{report.action_dim}D</b></div><div><span>Device</span><b>{report.device}</b></div></div><div className="check-grid">{Object.entries(report.checks).map(([name, passed]) => <div className={passed ? 'passed' : 'failed'} key={name}>{passed ? <Check /> : <X />}<span>{name.replace('_', ' ')}</span></div>)}</div><p className="muted">Camera keys: {report.camera_keys.join(', ') || 'none'} · Hardware connected: no</p></div>}</GlassCard><div className="joint-columns"><JointPanel title="Left A1Z" health={task.data?.health.can0} />{mode === 'dual' && <JointPanel title="Right A1Z" health={task.data?.health.can1} />}</div><GlassCard className="runtime-health"><StatusDot state={task.data?.health.top_rgb ?? 'unknown'} label="Top D435" /><StatusDot state={task.data?.health.left_wrist_rgb ?? 'unknown'} label={mode === 'dual' ? 'Left D405' : 'Wrist D405'} />{mode === 'dual' && <StatusDot state={task.data?.health.right_wrist_rgb ?? 'unknown'} label="Right D405" />}<span>Inference latency: N/A</span><span>Control FPS: N/A</span></GlassCard></div>
      <GlassCard className="inference-config"><div className="card-heading"><div><span className="eyebrow">SAFE TEST</span><h2>运行参数</h2></div><Cpu /></div><Field label="Preset"><div className="segmented compact">{(['safe', 'normal', 'custom'] as const).map((value) => <button className={preset === value ? 'active' : ''} onClick={() => choosePreset(value)} key={value}>{value}</button>)}</div></Field><Field label="Task instruction"><textarea rows={3} value={taskInstruction} onChange={(event) => setTaskInstruction(event.target.value)} /></Field><Field label="Inference"><select value={inferenceType} onChange={(event) => { setInferenceType(event.target.value as 'sync' | 'async'); setPreset('custom') }}><option value="sync">Sync（ACT 首次验证推荐）</option><option value="async">Async</option></select></Field>
        <div className="form-grid"><Field label="Left CAN"><select value={leftCan} onChange={(event) => setLeftCan(event.target.value as 'can0' | 'can1')}><option>can0</option><option>can1</option></select></Field>{mode === 'dual' && <Field label="Right CAN"><select value={rightCan} onChange={(event) => setRightCan(event.target.value as 'can0' | 'can1')}><option>can1</option><option>can0</option></select></Field>}</div><Field label="FPS"><input type="number" min={1} max={60} value={fps} onChange={(event) => setFps(Number(event.target.value))} /></Field><Field label="Duration" hint="首次验证建议 5–10 秒"><input type="number" min={1} max={3600} value={duration} onChange={(event) => { setDuration(Number(event.target.value)); setPreset('custom') }} /></Field>
        <Field label="Top D435 Serial"><input list="inference-camera-serials" value={topSerial} onChange={(event) => setTopSerial(event.target.value)} /></Field><Field label={mode === 'dual' ? 'Left D405 Serial' : 'Wrist D405 Serial'}><input list="inference-camera-serials" value={leftSerial} onChange={(event) => setLeftSerial(event.target.value)} /></Field>{mode === 'dual' && <Field label="Right D405 Serial"><input list="inference-camera-serials" value={rightSerial} onChange={(event) => setRightSerial(event.target.value)} /></Field>}<datalist id="inference-camera-serials">{(devices.data?.cameras ?? []).map((item) => <option key={item.serial} value={item.serial} />)}</datalist><div className="form-grid"><Field label="Camera Width"><input type="number" min={1} value={cameraWidth} onChange={(event) => setCameraWidth(Number(event.target.value))} /></Field><Field label="Camera Height"><input type="number" min={1} value={cameraHeight} onChange={(event) => setCameraHeight(Number(event.target.value))} /></Field></div>
        <Field label="Max joint delta" hint="Safe Test: 0.01 rad / step"><input type="number" min={0.001} max={0.5} step={0.005} value={delta} onChange={(event) => { setDelta(Number(event.target.value)); setPreset('custom') }} /></Field><Field label="EMA alpha"><input type="number" min={0} max={1} step={0.05} value={ema} onChange={(event) => setEma(Number(event.target.value))} /></Field><details><summary>Advanced Settings</summary><div className="switch-list"><label><input type="checkbox" checked={displayData} onChange={(event) => setDisplayData(event.target.checked)} />Rerun display_data</label><label><input type="checkbox" checked={returnHome} onChange={(event) => setReturnHome(event.target.checked)} />退出时返回 Home</label><label><input type="checkbox" checked={openGrippers} disabled={mode === 'single'} onChange={(event) => setOpenGrippers(event.target.checked)} />退出时张开夹爪</label></div></details><Field label="Gripper start hold"><input value="false（锁定）" readOnly /></Field><div className="notice">ACT 使用训练坐标系中的绝对夹爪目标，推理不可启用启动相对保持。</div><label className="safety-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><ShieldCheck /><span><b>确认推理安全检查</b>Compatibility、初始姿态、任务环境、Safe Test 与物理急停均已确认。</span></label><ErrorNotice error={guardedStart.error as Error | null} /><Button aria-label="开始安全推理" disabled={!report?.compatible || !confirmed || guardedStart.isPending || Boolean(taskId)} onClick={() => guardedStart.run(requestBody())}><Play size={17} />开始安全推理</Button><p className="muted">无 Pause：当前 A1Z 没有经过验证的软件 Hold 能力。运行时仅提供 Safe Stop。</p></GlassCard></div>
    <PreflightDialog report={guardedStart.report} onClose={guardedStart.closeReport} onContinueSimulation={guardedStart.continueSimulation} />
  </div>
}
