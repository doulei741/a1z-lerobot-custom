import { useQuery } from '@tanstack/react-query'
import { Camera, Play, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { JointPanel } from '../components/JointPanel'
import { PreflightDialog } from '../components/PreflightDialog'
import { Button, ErrorNotice, Field, GlassCard, PageTitle, Segmented, StatusDot } from '../components/ui'
import { usePreflightStart } from '../hooks/usePreflightStart'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'

const dualLeft = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.08975979] }
const dualRight = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975] }
const single = { signs: [-1, 1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.040418965, 1.567886653, -1.698370257, -0.144229406, -0.011507665, -0.016411362] }

export function Teleoperation() {
  const [mode, setMode] = useState<'single' | 'dual'>('dual')
  const [preset, setPreset] = useState<'safe' | 'normal' | 'custom'>('safe')
  const [confirmed, setConfirmed] = useState(false)
  const [fps, setFps] = useState(30)
  const [ema, setEma] = useState(0.3)
  const [delta, setDelta] = useState(0.01)
  const [leftPort, setLeftPort] = useState('/dev/ttyACM0')
  const [rightPort, setRightPort] = useState('/dev/ttyACM1')
  const [leftCan, setLeftCan] = useState<'can0' | 'can1'>('can0')
  const [rightCan, setRightCan] = useState<'can0' | 'can1'>('can1')
  const [leftLeaderId, setLeftLeaderId] = useState('a1z_left_leader')
  const [rightLeaderId, setRightLeaderId] = useState('a1z_right_leader')
  const [gripperHold, setGripperHold] = useState(false)
  const [returnHome, setReturnHome] = useState(false)
  const [openGrippers, setOpenGrippers] = useState(false)
  const [displayData, setDisplayData] = useState(false)
  const [displayCompressed, setDisplayCompressed] = useState(false)
  const [teleopDuration, setTeleopDuration] = useState<number | ''>('')
  const [cameraMode, setCameraMode] = useState<'none' | 'configured'>('none')
  const [topSerial, setTopSerial] = useState('025222071608')
  const [leftCameraSerial, setLeftCameraSerial] = useState('260522273365')
  const [rightCameraSerial, setRightCameraSerial] = useState('260522278763')
  const [cameraWidth, setCameraWidth] = useState(640)
  const [cameraHeight, setCameraHeight] = useState(480)
  const [cameraFps, setCameraFps] = useState(30)
  const [leftMapping, setLeftMapping] = useState(dualLeft)
  const [rightMapping, setRightMapping] = useState(dualRight)
  const setActive = usePlatformStore((state) => state.setActiveTask)
  const taskId = usePlatformStore((state) => state.activeTaskId)
  const task = useQuery({ queryKey: ['task', taskId], queryFn: () => api.task(taskId!), enabled: Boolean(taskId) })
  const profiles = useQuery({ queryKey: ['pairing-profiles'], queryFn: api.pairingProfiles })
  const devices = useQuery({ queryKey: ['devices'], queryFn: api.devices })
  const camera = (serial: string) => ({ serial, width: cameraWidth, height: cameraHeight, fps: cameraFps })
  const chooseCameraMode = (value: 'none' | 'configured') => {
    setCameraMode(value)
    if (value === 'configured') setDisplayData(true)
  }
  const requestBody = () => ({ mode, left_can: leftCan, right_can: rightCan, fps, ema_alpha: ema, max_joint_delta: delta, gripper_start_hold: gripperHold, return_home_on_disconnect: returnHome, open_grippers_on_disconnect: openGrippers, display_data: displayData, display_compressed_images: displayCompressed, teleop_time_s: teleopDuration === '' ? null : teleopDuration, safety_confirmed: confirmed, left_leader_port: leftPort, right_leader_port: rightPort, left_leader_id: leftLeaderId, right_leader_id: rightLeaderId, left_mapping: leftMapping, right_mapping: rightMapping, cameras: cameraMode === 'none' ? {} : mode === 'dual' ? { top_rgb: camera(topSerial), left_wrist_rgb: camera(leftCameraSerial), right_wrist_rgb: camera(rightCameraSerial) } : { top_rgb: camera(topSerial), wrist_rgb: camera(leftCameraSerial) } })
  const guardedStart = usePreflightStart(api.preflightTeleop, api.startTeleop, (result) => setActive(result.task_id, result.task_type))
  const choosePreset = (value: typeof preset) => { setPreset(value); if (value === 'safe') { setEma(0.3); setDelta(0.01) } else if (value === 'normal') { setEma(0.3); setDelta(0.05) } }
  return <div className="page">
    <PageTitle title="遥控操作" description="Leader 读取与 A1Z 控制保留在原始 LeRobot 进程中；页面仅管理参数、状态与安全停止。" />
    <div className="teleop-layout">
      <GlassCard className="config-card"><div className="card-heading"><div><span className="eyebrow">CONFIGURATION</span><h2>运行前配置</h2></div><StatusDot state={task.data?.status === 'ready' ? 'healthy' : 'unknown'} label={task.data?.status ?? '未运行'} /></div>
        <Segmented value={mode} onChange={(value) => { setMode(value); setLeftMapping(value === 'single' ? single : dualLeft) }} />
        <Field label="Preset"><div className="segmented compact">{(['safe', 'normal', 'custom'] as const).map((value) => <button className={preset === value ? 'active' : ''} onClick={() => choosePreset(value)} key={value}>{value === 'safe' ? 'Safe' : value === 'normal' ? 'Normal' : 'Custom'}</button>)}</div></Field>
        <div className="form-grid"><Field label="Left CAN"><select value={leftCan} onChange={(event) => setLeftCan(event.target.value as 'can0' | 'can1')}><option>can0</option><option>can1</option></select></Field>{mode === 'dual' && <Field label="Right CAN"><select value={rightCan} onChange={(event) => setRightCan(event.target.value as 'can0' | 'can1')}><option>can1</option><option>can0</option></select></Field>}<Field label="Left Leader Port"><select value={leftPort} onChange={(event) => setLeftPort(event.target.value)}>{(devices.data?.leaders ?? []).map((item) => <option key={item.port}>{item.port}</option>)}{!(devices.data?.leaders ?? []).some((item) => item.port === leftPort) && <option>{leftPort}</option>}</select></Field>{mode === 'dual' && <Field label="Right Leader Port"><select value={rightPort} onChange={(event) => setRightPort(event.target.value)}>{(devices.data?.leaders ?? []).map((item) => <option key={item.port}>{item.port}</option>)}{!(devices.data?.leaders ?? []).some((item) => item.port === rightPort) && <option>{rightPort}</option>}</select></Field>}<Field label="Left Leader ID"><input value={leftLeaderId} onChange={(event) => setLeftLeaderId(event.target.value)} /></Field>{mode === 'dual' && <Field label="Right Leader ID"><input value={rightLeaderId} onChange={(event) => setRightLeaderId(event.target.value)} /></Field>}<Field label="FPS" hint="LeRobot outer loop"><input type="number" value={fps} min={1} max={60} onChange={(event) => setFps(Number(event.target.value))} /></Field><Field label="EMA α" hint="0–1"><input type="number" value={ema} step="0.05" min={0} max={1} onChange={(event) => setEma(Number(event.target.value))} /></Field><Field label="Max joint delta" hint="rad / step"><input type="number" value={delta} step="0.005" min={0.001} max={0.5} onChange={(event) => { setDelta(Number(event.target.value)); setPreset('custom') }} /></Field></div>
        <Field label="Camera"><select value={cameraMode} onChange={(event) => chooseCameraMode(event.target.value as 'none' | 'configured')}><option value="none">No camera</option><option value="configured">Configured RGB cameras</option></select></Field>
        <div className="switch-list"><label><input aria-label="Open Rerun viewer" type="checkbox" checked={displayData} onChange={(event) => setDisplayData(event.target.checked)} />打开 Rerun 实时观察窗口</label></div>
        {cameraMode === 'configured' && <><div className="notice">已启用 RGB 相机，并自动开启 Rerun。启动遥控后，画面会显示在独立的 Rerun Viewer 窗口中，不会嵌入浏览器页面。</div><div className="form-grid"><Field label="Top D435"><input list="teleop-camera-serials" value={topSerial} onChange={(event) => setTopSerial(event.target.value)} /></Field><Field label={mode === 'dual' ? 'Left D405' : 'Wrist D405'}><input list="teleop-camera-serials" value={leftCameraSerial} onChange={(event) => setLeftCameraSerial(event.target.value)} /></Field>{mode === 'dual' && <Field label="Right D405"><input list="teleop-camera-serials" value={rightCameraSerial} onChange={(event) => setRightCameraSerial(event.target.value)} /></Field>}<Field label="Camera Width"><input type="number" min={160} max={1920} value={cameraWidth} onChange={(event) => setCameraWidth(Number(event.target.value))} /></Field><Field label="Camera Height"><input type="number" min={120} max={1080} value={cameraHeight} onChange={(event) => setCameraHeight(Number(event.target.value))} /></Field><Field label="Camera FPS"><input type="number" min={1} max={60} value={cameraFps} onChange={(event) => setCameraFps(Number(event.target.value))} /></Field></div><datalist id="teleop-camera-serials">{(devices.data?.cameras ?? []).map((item) => <option value={item.serial} key={item.serial} />)}</datalist></>}
        <details><summary>Advanced Settings</summary><div className="switch-list"><label><input aria-label="Gripper start hold" type="checkbox" checked={gripperHold} onChange={(event) => setGripperHold(event.target.checked)} />Gripper start hold（默认关闭，使用绝对夹爪映射）</label><label><input type="checkbox" checked={returnHome} onChange={(event) => setReturnHome(event.target.checked)} />退出时返回 Home</label><label><input type="checkbox" checked={openGrippers} disabled={mode === 'single'} onChange={(event) => setOpenGrippers(event.target.checked)} />退出时张开夹爪（仅双臂支持）</label><label><input aria-label="Display compressed images" type="checkbox" checked={displayCompressed} disabled={!displayData} onChange={(event) => setDisplayCompressed(event.target.checked)} />Display compressed images</label></div><Field label="Teleoperation duration" hint="留空表示持续运行，直到 Safe Stop"><input aria-label="Teleoperation duration" type="number" min={1} max={86400} placeholder="无限" value={teleopDuration} onChange={(event) => setTeleopDuration(event.target.value === '' ? '' : Number(event.target.value))} /></Field><div className="notice">关闭 Gripper start hold 时，Follower 直接使用 Leader 的绝对夹爪目标；启动前应确认两侧夹爪姿态对应。</div><Field label="Pairing Profile"><select defaultValue="" onChange={(event) => { const profile = profiles.data?.items.find((item) => item.profile_id === event.target.value); if (!profile) return; const mapping = { signs: profile.signs, scales: profile.scales, offsets_rad: profile.offsets_rad }; if (profile.side === 'left') setLeftMapping(mapping); else setRightMapping(mapping) }}><option value="">当前现场验证默认值</option>{profiles.data?.items.map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.profile_id} · {profile.side}</option>)}</select></Field><div className="mapping-table"><span>Joint</span><span>Sign</span><span>Scale</span><span>Offset rad</span>{leftMapping.signs.map((sign, index) => <div className="mapping-row" key={index}><b>J{index + 1}</b><input type="number" value={sign} step="2" onChange={(event) => setLeftMapping({ ...leftMapping, signs: leftMapping.signs.map((value, item) => item === index ? Number(event.target.value) : value) })} /><input type="number" value={leftMapping.scales[index]} step="0.01" onChange={(event) => setLeftMapping({ ...leftMapping, scales: leftMapping.scales.map((value, item) => item === index ? Number(event.target.value) : value) })} /><input type="number" value={leftMapping.offsets_rad[index]} step="0.001" onChange={(event) => setLeftMapping({ ...leftMapping, offsets_rad: leftMapping.offsets_rad.map((value, item) => item === index ? Number(event.target.value) : value) })} /></div>)}</div><p className="muted">显示当前左臂或 Single 映射；右臂使用独立已验证默认值或所选右侧 Profile。</p></details>
        <label className="safety-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><ShieldCheck /><span><b>确认运动安全检查</b>工作区无人员/障碍、CAN 映射和配对正确、物理急停可用。</span></label>
        <ErrorNotice error={guardedStart.error as Error | null} /><Button disabled={!confirmed || guardedStart.isPending || Boolean(taskId)} onClick={() => guardedStart.run(requestBody())}><Play size={17} />Start Teleoperation</Button>
      </GlassCard>
      <div className="runtime-column"><div className="joint-columns"><JointPanel title="Left A1Z" health={task.data?.health.can0} />{mode === 'dual' && <JointPanel title="Right A1Z" health={task.data?.health.can1} />}</div><GlassCard className="camera-strip"><Camera /><div><strong>Rerun 实时观察</strong><p>任务进程拥有相机。Web 后端不会重复打开 RealSense；启用 display_data 后请在独立 Rerun Viewer 中观察。</p></div></GlassCard></div>
    </div>
    <PreflightDialog report={guardedStart.report} onClose={guardedStart.closeReport} onContinueSimulation={guardedStart.continueSimulation} />
  </div>
}
