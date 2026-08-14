import { useMutation, useQuery } from '@tanstack/react-query'
import { Check, ChevronRight, Link2, Save, ShieldCheck, Usb } from 'lucide-react'
import { useState } from 'react'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import { Button, ErrorNotice, Field, GlassCard, PageTitle, StatusDot } from '../components/ui'
import { PreflightDialog } from '../components/PreflightDialog'
import { usePreflightStart } from '../hooks/usePreflightStart'

const motors = ['arm_0', 'arm_1', 'arm_2', 'arm_3', 'arm_4', 'arm_5', 'gripper']
const defaultSigns = [-1, -1, 1, 1, 1, -1]
const defaultScales = [1, 1, 1, 1, 1, 1]

interface PairingResult {
  leader_rad: number[]
  follower_rad: number[]
  signs: number[]
  scales: number[]
  offsets_rad: number[]
}

export function Calibration() {
  const setActive = usePlatformStore((state) => state.setActiveTask)
  const activeId = usePlatformStore((state) => state.activeTaskId)
  const activeTask = useQuery({ queryKey: ['task', activeId], queryFn: () => api.task(activeId!), enabled: Boolean(activeId) })
  const [side, setSide] = useState<'left' | 'right'>('left')
  const [port, setPort] = useState('/dev/ttyACM0')
  const [leaderId, setLeaderId] = useState('a1z_left_leader')
  const [phase, setPhase] = useState('idle')
  const [ranges, setRanges] = useState<Record<string, { min: number; max: number }>>({})
  const [pairConfirmed, setPairConfirmed] = useState(false)
  const [pairing, setPairing] = useState<PairingResult | null>(null)
  const [savedOffsets, setSavedOffsets] = useState<number[] | null>(null)
  const calibrationStatus = useQuery({ queryKey: ['calibration-status', leaderId], queryFn: () => api.calibrationStatus(leaderId) })
  const profiles = useQuery({ queryKey: ['pairing-profiles'], queryFn: api.pairingProfiles })
  const calibrationRequest = () => ({ side, port, leader_id: leaderId })
  const guardedCalibration = usePreflightStart(api.preflightCalibration, api.startCalibration, (task) => { setActive(task.task_id, task.task_type); setPhase('waiting_middle') })
  const action = useMutation({ mutationFn: async (name: string) => {
    if (!activeId) throw new Error('请先启动校准')
    const result = await api.calibrationAction(activeId, name, crypto.randomUUID())
    if (typeof result.calibration_phase === 'string') setPhase(result.calibration_phase)
    if (result.ranges && typeof result.ranges === 'object') setRanges(result.ranges as Record<string, { min: number; max: number }>)
    return result
  } })
  const pairingRequest = () => ({ side, leader_port: port, leader_id: leaderId, can_interface: side === 'left' ? 'can0' : 'can1', signs: defaultSigns, scales: defaultScales, safety_confirmed: pairConfirmed })
  const guardedPairing = usePreflightStart(api.preflightPairing, api.pairingRead, (task) => {
      setActive(task.task_id, task.task_type)
      const value = task.metadata?.pairing_result
      if (value && typeof value === 'object') setPairing(value as unknown as PairingResult)
  })
  const savePairing = useMutation({
    mutationFn: () => {
      if (!pairing) throw new Error('请先读取配对姿态')
      return api.pairingSave({ ...pairing, side, profile_id: `a1z_${side}_pair`, leader_id: leaderId, can_interface: side === 'left' ? 'can0' : 'can1' })
    }, onSuccess: () => setSavedOffsets(pairing?.offsets_rad ?? null),
  })
  const verifyPairing = useMutation({
    mutationFn: () => {
      if (!pairing) throw new Error('请先读取配对姿态')
      const persisted = profiles.data?.items.find((item) => item.profile_id === `a1z_${side}_pair`)
      return api.pairingVerify({ ...pairing, side, offsets_rad: savedOffsets ?? persisted?.offsets_rad ?? pairing.offsets_rad, tolerance_rad: 0.05 })
    },
  })
  const selectSide = (value: 'left' | 'right') => {
    setSide(value)
    setPort(value === 'left' ? '/dev/ttyACM0' : '/dev/ttyACM1')
    setLeaderId(value === 'left' ? 'a1z_left_leader' : 'a1z_right_leader')
    setPhase('idle')
    setRanges({})
    setPairing(null)
    setSavedOffsets(null)
    verifyPairing.reset()
  }
  const displayedPhase = activeId ? activeTask.data?.phase ?? phase : phase
  return <div className="page calibration-page">
    <PageTitle title="机械臂校准" description="校准 Leader 编码器范围，并独立管理 Leader / Follower 配对映射。" />
    <div className="stepper">{['Leader 校准', 'Leader / Follower 配对', '验证', '完成'].map((label, index) => <div className={index === 0 ? 'active' : ''} key={label}><span>{index + 1}</span><b>{label}</b>{index < 3 && <ChevronRight size={17} />}</div>)}</div>
    <div className="two-column">
      <GlassCard>
        <div className="card-heading"><div><span className="eyebrow">LEADER</span><h2>{side === 'left' ? 'Left Leader' : 'Right Leader'}</h2></div><StatusDot state={activeTask.data?.status === 'ready' ? 'healthy' : 'unknown'} label={displayedPhase} /></div>
        <div className="segmented compact"><button className={side === 'left' ? 'active' : ''} onClick={() => selectSide('left')}>LEFT</button><button className={side === 'right' ? 'active' : ''} onClick={() => selectSide('right')}>RIGHT</button></div>
        <Field label="Serial Port"><div className="input-icon"><Usb size={16} /><input value={port} onChange={(event) => setPort(event.target.value)} /></div></Field>
        <Field label="Leader ID" hint="左右必须使用不同 calibration id"><input value={leaderId} onChange={(event) => setLeaderId(event.target.value)} /></Field>
        <div className="notice"><b>{calibrationStatus.data?.exists ? '已有校准可直接使用' : '未发现校准文件'}</b>{calibrationStatus.data?.path ?? '正在检查…'}</div>
        <div className="instruction"><strong>{phase === 'waiting_middle' ? '将所有关节移到机械行程中点' : phase === 'recording_range' ? '逐一走完整 J1–J6 与夹爪范围' : '流程由现有 A1ZLeader 校准逻辑执行'}</strong><p>Follower 零位维护不在本页面提供，请使用高级维护工具与终端。</p></div>
        <ErrorNotice error={(guardedCalibration.error ?? action.error) as Error | null} />
        <div className="actions">
          {phase === 'idle' && <Button onClick={() => guardedCalibration.run(calibrationRequest())} disabled={guardedCalibration.isPending || Boolean(activeId)}>{calibrationStatus.data?.exists ? '重新校准' : '开始校准'}</Button>}
          {phase === 'waiting_middle' && <Button onClick={() => action.mutate('middle')}>确认中位并写入 Half-turn Homing</Button>}
          {phase === 'waiting_range' && <Button onClick={() => action.mutate('record-range')}>开始记录全行程</Button>}
          {phase === 'recording_range' && <Button onClick={() => action.mutate('stop-range')}>停止范围记录</Button>}
          {phase === 'review' && <Button onClick={() => action.mutate('save')}><Save size={16} />保存 MotorCalibration</Button>}
          {phase === 'completed' && <div className="success"><Check size={18} />校准文件已保存</div>}
        </div>
      </GlassCard>
      <GlassCard>
        <div className="card-heading"><div><span className="eyebrow">LIVE RANGE</span><h2>关节范围</h2></div><span className="subtle">raw encoder</span></div>
        <div className="range-table"><div className="range-head"><span>Joint</span><span>Min</span><span>Max</span><span>Span</span></div>{motors.map((motor) => { const range = ranges[motor]; return <div key={motor}><strong>{motor === 'gripper' ? 'Gripper' : `J${Number(motor.split('_')[1]) + 1}`}</strong><span>{range?.min ?? '—'}</span><span>{range?.max ?? '—'}</span><span>{range ? range.max - range.min : '—'}</span></div> })}</div>
        <div className="pairing-callout"><Link2 /><div><strong>Pairing 与 Leader 校准分离</strong><p>目标 = Leader(rad) × scale × sign + offset。映射 Profile 不写入 MotorCalibration JSON。</p></div></div>
      </GlassCard>
    </div>
    <GlassCard className="pairing-panel">
      <div className="card-heading"><div><span className="eyebrow">PAIRING PROFILE</span><h2>{side === 'left' ? '左臂' : '右臂'} Leader / Follower 配对</h2></div><StatusDot state={savePairing.isSuccess ? 'healthy' : pairing ? 'degraded' : 'unknown'} label={savePairing.isSuccess ? 'Saved' : pairing ? 'Review' : 'Not read'} /></div>
      <div className="pairing-grid"><div><Field label="Leader"><input value={`${leaderId} · ${port}`} readOnly /></Field><Field label="Follower"><input value={`${side === 'left' ? 'can0' : 'can1'} · A1Z ${side}`} readOnly /></Field><label className="safety-check"><input type="checkbox" checked={pairConfirmed} onChange={(event) => setPairConfirmed(event.target.checked)} /><ShieldCheck /><span><b>同一安全姿态已确认</b>两臂周围无障碍物，物理急停可用。读取会短暂连接 Follower。</span></label><Button disabled={!pairConfirmed || guardedPairing.isPending || Boolean(activeId)} onClick={() => guardedPairing.run(pairingRequest())}><Link2 size={16} />读取 6D 并计算 Offset</Button><ErrorNotice error={(guardedPairing.error ?? savePairing.error) as Error | null} /></div><div className="range-table"><div className="range-head"><span>Joint</span><span>Leader</span><span>Follower</span><span>Offset</span></div>{Array.from({ length: 6 }, (_, index) => <div key={index}><strong>J{index + 1}</strong><span>{pairing?.leader_rad[index]?.toFixed(3) ?? '—'}</span><span>{pairing?.follower_rad[index]?.toFixed(3) ?? '—'}</span><span>{pairing?.offsets_rad[index]?.toFixed(3) ?? '—'}</span></div>)}</div></div>
      <div className="actions"><Button variant="secondary" disabled={!pairing || verifyPairing.isPending} onClick={() => verifyPairing.mutate()}><Check size={16} />用已保存 Offset 验证 0.05 rad</Button><Button variant="secondary" disabled={!pairing || savePairing.isPending || verifyPairing.data?.verified === false} onClick={() => savePairing.mutate()}><Save size={16} />保存独立 Pairing Profile</Button></div>{verifyPairing.data && <div className="notice"><b>{verifyPairing.data.verified ? 'VERIFY PASSED' : 'VERIFY FAILED'}</b>各轴误差：{verifyPairing.data.errors_rad.map((value) => value.toFixed(3)).join(' · ')} rad。保存后可将两臂移到另一相同姿态、重新读取并再次验证。</div>}
    </GlassCard>
    <PreflightDialog report={guardedCalibration.report} onClose={guardedCalibration.closeReport} onContinueSimulation={guardedCalibration.continueSimulation} />
    <PreflightDialog report={guardedPairing.report} onClose={guardedPairing.closeReport} onContinueSimulation={guardedPairing.continueSimulation} />
  </div>
}
