import { useMutation, useQuery } from '@tanstack/react-query'
import { FastForward, RotateCcw, Save, ShieldCheck, Square, Video } from 'lucide-react'
import { useState } from 'react'
import { Button, ErrorNotice, Field, GlassCard, PageTitle, Segmented } from '../components/ui'
import { PreflightDialog } from '../components/PreflightDialog'
import { RerunPreview } from '../components/RerunPreview'
import { usePreflightStart } from '../hooks/usePreflightStart'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'

const dualLeft = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [0.185504249, 1.676119148, -1.985360469, 0.471459368, 0.061374215, 0.08975979] }
const dualRight = { signs: [-1, -1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.097389546, 1.672050437, -1.971852804, 0.520146476, -0.038316864, -0.021480975] }
const singleMapping = { signs: [-1, 1, 1, 1, 1, -1], scales: [1, 1, 1, 1, 1, 1], offsets_rad: [-0.040418965, 1.567886653, -1.698370257, -0.144229406, -0.011507665, -0.016411362] }

function formatCountdown(seconds: number | null | undefined) {
  if (seconds == null) return '--:--'
  const safe = Math.max(0, Math.floor(seconds))
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`
}

export function Recording() {
  const [confirmed, setConfirmed] = useState(false)
  const [mode, setMode] = useState<'single' | 'dual'>('dual')
  const [repoId, setRepoId] = useState('local/a1z_dual_web')
  const [root, setRoot] = useState('datasets/a1z_dual_web')
  const [configPath, setConfigPath] = useState('a1z_lerobot/configs/record_a1z_dual_realsense.yaml')
  const [taskText, setTaskText] = useState('Coordinate both arms to complete the configured task')
  const [episodes, setEpisodes] = useState(15)
  const [resume, setResume] = useState(false)
  const [targetEpisodes, setTargetEpisodes] = useState(15)
  const [resumeExistingEpisodes, setResumeExistingEpisodes] = useState(0)
  const [resumeCompatibilityChecked, setResumeCompatibilityChecked] = useState(false)
  const [rightWristSerial, setRightWristSerial] = useState('260522278763')
  const [topSerial, setTopSerial] = useState('025222071608')
  const [leftWristSerial, setLeftWristSerial] = useState('260522273365')
  const [topCameraEnabled, setTopCameraEnabled] = useState(true)
  const [leftCameraEnabled, setLeftCameraEnabled] = useState(true)
  const [rightCameraEnabled, setRightCameraEnabled] = useState(true)
  const [leftCan, setLeftCan] = useState<'can0' | 'can1'>('can0')
  const [rightCan, setRightCan] = useState<'can0' | 'can1'>('can1')
  const [leftLeaderPort, setLeftLeaderPort] = useState('/dev/ttyACM0')
  const [rightLeaderPort, setRightLeaderPort] = useState('/dev/ttyACM1')
  const [leftLeaderId, setLeftLeaderId] = useState('a1z_left_leader')
  const [rightLeaderId, setRightLeaderId] = useState('a1z_right_leader')
  const [episodeTime, setEpisodeTime] = useState(60)
  const [resetTime, setResetTime] = useState(10)
  const [fps, setFps] = useState(30)
  const [ema, setEma] = useState(0.3)
  const [delta, setDelta] = useState(0.05)
  const [gripperHold, setGripperHold] = useState(false)
  const [returnHome, setReturnHome] = useState(false)
  const [openGrippers, setOpenGrippers] = useState(false)
  const [displayData, setDisplayData] = useState(true)
  const [displayCompressed, setDisplayCompressed] = useState(false)
  const [video, setVideo] = useState(true)
  const [playSounds, setPlaySounds] = useState(false)
  const [writerProcesses, setWriterProcesses] = useState(0)
  const [writerThreads, setWriterThreads] = useState(4)
  const [videoBatchSize, setVideoBatchSize] = useState(1)
  const [streamingEncoding, setStreamingEncoding] = useState(false)
  const [encoderQueueSize, setEncoderQueueSize] = useState(30)
  const [encoderThreads, setEncoderThreads] = useState<number | ''>('')
  const [encoderCodec, setEncoderCodec] = useState('libsvtav1')
  const [encoderCrf, setEncoderCrf] = useState(30)
  const [encoderPreset, setEncoderPreset] = useState(12)
  const [encoderGop, setEncoderGop] = useState(2)
  const [encoderFastDecode, setEncoderFastDecode] = useState(0)
  const [cameraWidth, setCameraWidth] = useState(640)
  const [cameraHeight, setCameraHeight] = useState(480)
  const [leftMapping, setLeftMapping] = useState(dualLeft)
  const [rightMapping, setRightMapping] = useState(dualRight)
  const setActive = usePlatformStore((state) => state.setActiveTask)
  const taskId = usePlatformStore((state) => state.activeTaskId)
  const task = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => api.task(taskId!),
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return !status || ['created', 'starting', 'ready', 'running', 'stopping'].includes(status) ? 500 : false
    },
  })
  const profiles = useQuery({ queryKey: ['pairing-profiles'], queryFn: api.pairingProfiles })
  const devices = useQuery({ queryKey: ['devices'], queryFn: api.devices })
  const camera = (serial: string, enabled: boolean) => ({ enabled, serial, width: cameraWidth, height: cameraHeight, fps, use_depth: false })
  const selectedCameras = mode === 'dual'
    ? { top_rgb: camera(topSerial, topCameraEnabled), left_wrist_rgb: camera(leftWristSerial, leftCameraEnabled), right_wrist_rgb: camera(rightWristSerial, rightCameraEnabled) }
    : { top_rgb: camera(topSerial, topCameraEnabled), wrist_rgb: camera(leftWristSerial, leftCameraEnabled) }
  const cameraNames = Object.entries(selectedCameras).filter(([, value]) => value.enabled).map(([name]) => name)
  const existingEpisodes = resumeExistingEpisodes
  const addEpisodes = resume && resumeCompatibilityChecked ? Math.max(0, targetEpisodes - existingEpisodes) : episodes
  const requestBody = () => ({
    mode, config_path: configPath, safety_confirmed: confirmed, resume, right_wrist_serial: rightWristSerial,
    left_can: leftCan, right_can: rightCan, left_leader_port: leftLeaderPort,
    right_leader_port: rightLeaderPort, left_leader_id: leftLeaderId, right_leader_id: rightLeaderId,
    ema_alpha: ema, max_joint_delta: delta, gripper_start_hold: gripperHold,
    return_home_on_disconnect: returnHome, open_grippers_on_disconnect: openGrippers,
    display_data: displayData, display_compressed_images: displayCompressed, play_sounds: playSounds, fps,
    cameras: selectedCameras,
    left_mapping: leftMapping, right_mapping: rightMapping,
    dataset: {
      repo_id: repoId, root, single_task: taskText, num_episodes: addEpisodes,
      episode_time_s: episodeTime, reset_time_s: resetTime, fps, video,
      num_image_writer_processes: writerProcesses,
      num_image_writer_threads_per_camera: writerThreads,
      video_encoding_batch_size: videoBatchSize,
      streaming_encoding: streamingEncoding,
      encoder_queue_maxsize: encoderQueueSize,
      encoder_threads: encoderThreads === '' ? null : encoderThreads,
      camera_encoder: { vcodec: encoderCodec, pix_fmt: 'yuv420p', g: encoderGop, crf: encoderCrf, preset: encoderPreset, fast_decode: encoderFastDecode, video_backend: 'pyav' },
    },
  })
  const compatibility = useMutation({
    mutationFn: () => api.recordCompatibility(requestBody()),
    onSuccess: (report) => {
      setResumeExistingEpisodes(report.existing_episodes)
      setTargetEpisodes(report.existing_episodes + episodes)
      setResumeCompatibilityChecked(true)
    },
  })
  const guardedStart = usePreflightStart(api.preflightRecord, api.startRecord, (result) => setActive(result.task_id, result.task_type))
  const command = useMutation({ mutationFn: (action: string) => api.recordAction(taskId!, action, crypto.randomUUID(), task.data?.episode_index ?? 0), onSuccess: () => void task.refetch() })
  const normalStop = useMutation({
    mutationFn: () => api.stopRecord(taskId!),
    onSuccess: () => setActive(null),
  })
  const taskIsRecording = task.data?.task_type === 'recording'
  const taskIsActive = Boolean(taskId && (!task.data || ['created', 'starting', 'ready', 'running', 'stopping'].includes(task.data.status)))
  const workerReady = taskIsRecording && ['ready', 'running'].includes(task.data?.status ?? '')
  const phase = taskIsRecording
    ? workerReady ? task.data?.record_phase ?? 'ready' : task.data?.record_phase === 'fault' ? 'fault' : task.data?.status ?? 'starting'
    : 'idle'
  const existing = task.data?.existing_episodes ?? existingEpisodes
  const isRecording = phase === 'recording'
  return <div className="page">
    <PageTitle title="数据录制" description="显式 Episode 协议管理保存、重录、Reset 与 Quick Next，每个动作均受状态机约束。" />
    <div className={`record-countdown ${isRecording ? 'countdown-active' : ''}`}><span>本轮剩余</span><strong>{formatCountdown(task.data?.remaining_time_s)}</strong><small>{isRecording ? `共 ${task.data?.episode_time_s ?? episodeTime} 秒` : '开始 Episode 后计时'}</small></div>
    <div className="record-layout">
      <div className="record-main"><GlassCard className="record-status"><div className="card-heading"><div><span className="eyebrow">RECORD PROTOCOL</span><h2>Episode Session</h2></div><span className={`phase phase-${phase}`}>{phase.toUpperCase()}</span></div><div className="episode-stats"><div><span>Existing Episodes</span><strong>{existing}</strong></div><div><span>Add Episodes</span><strong>{task.data?.add_episodes ?? addEpisodes}</strong></div><div><span>Total After Session</span><strong>{task.data?.total_after_session ?? existing + addEpisodes}</strong></div><div><span>Current Frames</span><strong>{task.data?.frames ?? 0}</strong></div></div>{phase === 'saving' && <div className="notice"><b>正在保存 Episode 并编码视频</b><br />保存完成前操作暂时锁定；完成后会自动进入重置阶段，达到本次 Episode 数量时会自动结束任务。</div>}{task.data?.fault_reason && <div className="notice notice-error"><b>FAULT</b>{task.data.fault_reason}<br />最后可信 Episode：{task.data.last_trusted_episode}；当前 Episode {task.data.current_episode_invalid ? '已作废' : '未作废'}。</div>}<div className="record-controls"><Button disabled={!workerReady || phase !== 'ready' || command.isPending} onClick={() => command.mutate('start-episode')}><Video size={16} />开始本轮 Episode</Button><Button variant="secondary" disabled={!isRecording || (task.data?.frames ?? 0) < 1 || command.isPending} onClick={() => command.mutate('finish-episode')}><Save size={16} />提前结束并保存</Button><Button variant="secondary" disabled={!isRecording || command.isPending} onClick={() => command.mutate('rerecord')}><RotateCcw size={16} />丢弃本轮并重录</Button><Button variant="secondary" disabled={!isRecording || (task.data?.frames ?? 0) < 1 || command.isPending} onClick={() => command.mutate('quick-next')}><FastForward size={16} />快速开始下一轮</Button>{phase === 'resetting' && <Button onClick={() => command.mutate('reset-done')}>重置完成</Button>}<Button variant="danger" disabled={!taskIsRecording || !taskIsActive || phase === 'saving' || normalStop.isPending} onClick={() => normalStop.mutate()}><Square size={15} />正常停止整个任务</Button>{task.data?.mock && <Button variant="secondary" disabled={!isRecording} onClick={() => api.mockFrame(taskId!)}>模拟一帧</Button>}</div><p className="muted">提前结束并保存：当前帧写入一个有效 Episode。丢弃并重录：放弃当前未保存帧并保持同一轮。正常停止：保留已保存 Episode、丢弃当前未保存帧并安全断开；saving 阶段会等待原子保存完成。Quick Next 不会跳过保存。</p></GlassCard>
        <RerunPreview task={task.data?.task_type === 'recording' ? task.data : undefined} cameraNames={cameraNames} /></div>
      <GlassCard className="record-config"><div className="card-heading"><div><span className="eyebrow">DATASET</span><h2>录制配置</h2></div></div><Segmented value={mode} onChange={(value) => { setMode(value); setConfigPath(value === 'single' ? 'a1z_lerobot/configs/record_a1z_single_realsense.yaml' : 'a1z_lerobot/configs/record_a1z_dual_realsense.yaml'); setLeftMapping(value === 'single' ? singleMapping : dualLeft); compatibility.reset() }} />
        <Field label="Config Path"><input value={configPath} onChange={(event) => { setConfigPath(event.target.value); compatibility.reset() }} /></Field><Field label="Repository ID"><input value={repoId} onChange={(event) => { setRepoId(event.target.value); compatibility.reset() }} /></Field><Field label="Dataset Root"><input value={root} onChange={(event) => { setRoot(event.target.value); compatibility.reset() }} /></Field>
        <div className="form-grid"><Field label="Left CAN"><select value={leftCan} onChange={(event) => setLeftCan(event.target.value as 'can0' | 'can1')}><option>can0</option><option>can1</option></select></Field>{mode === 'dual' && <Field label="Right CAN"><select value={rightCan} onChange={(event) => setRightCan(event.target.value as 'can0' | 'can1')}><option>can1</option><option>can0</option></select></Field>}</div>
        <Field label="Left Leader Port"><select value={leftLeaderPort} onChange={(event) => setLeftLeaderPort(event.target.value)}>{(devices.data?.leaders ?? []).map((item) => <option key={item.port}>{item.port}</option>)}{!(devices.data?.leaders ?? []).some((item) => item.port === leftLeaderPort) && <option>{leftLeaderPort}</option>}</select></Field><Field label="Left Leader ID"><input value={leftLeaderId} onChange={(event) => setLeftLeaderId(event.target.value)} /></Field>
        {mode === 'dual' && <><Field label="Right Leader Port"><select value={rightLeaderPort} onChange={(event) => setRightLeaderPort(event.target.value)}>{(devices.data?.leaders ?? []).map((item) => <option key={item.port}>{item.port}</option>)}{!(devices.data?.leaders ?? []).some((item) => item.port === rightLeaderPort) && <option>{rightLeaderPort}</option>}</select></Field><Field label="Right Leader ID"><input value={rightLeaderId} onChange={(event) => setRightLeaderId(event.target.value)} /></Field></>}
        <Field label="Pairing Profiles"><select defaultValue="" onChange={(event) => { const profile = profiles.data?.items.find((item) => item.profile_id === event.target.value); if (!profile) return; const mapping = { signs: profile.signs, scales: profile.scales, offsets_rad: profile.offsets_rad }; if (profile.side === 'left') setLeftMapping(mapping); else setRightMapping(mapping); compatibility.reset() }}><option value="">现场验证默认值</option>{profiles.data?.items.filter((profile) => mode === 'dual' || profile.side === 'left').map((profile) => <option key={profile.profile_id} value={profile.profile_id}>{profile.profile_id} · {profile.side}</option>)}</select></Field>
        <Field label="Task"><textarea rows={4} value={taskText} onChange={(event) => setTaskText(event.target.value)} /></Field>{!resume && <Field label="计划录制 Episode"><input type="number" min={1} value={episodes} onChange={(event) => { const value = Number(event.target.value); setEpisodes(value); setTargetEpisodes(value) }} /></Field>}<div className="form-grid"><Field label="Episode Time"><input type="number" min={1} value={episodeTime} onChange={(event) => setEpisodeTime(Number(event.target.value))} /></Field><Field label="Reset Time"><input type="number" min={0} value={resetTime} onChange={(event) => setResetTime(Number(event.target.value))} /></Field></div>
        <div className="switch-list"><label><input aria-label="Record top camera" type="checkbox" checked={topCameraEnabled} onChange={(event) => { setTopCameraEnabled(event.target.checked); compatibility.reset() }} />录制 Top D435</label><label><input aria-label="Record left wrist camera" type="checkbox" checked={leftCameraEnabled} onChange={(event) => { setLeftCameraEnabled(event.target.checked); compatibility.reset() }} />录制 {mode === 'dual' ? 'Left D405' : 'Wrist D405'}</label>{mode === 'dual' && <label><input aria-label="Record right wrist camera" type="checkbox" checked={rightCameraEnabled} onChange={(event) => { setRightCameraEnabled(event.target.checked); compatibility.reset() }} />录制 Right D405</label>}</div><Field label="Top D435 Serial"><input list="record-camera-serials" value={topSerial} disabled={!topCameraEnabled} onChange={(event) => setTopSerial(event.target.value)} /></Field><Field label={mode === 'dual' ? 'Left D405 Serial' : 'Wrist D405 Serial'}><input list="record-camera-serials" value={leftWristSerial} disabled={!leftCameraEnabled} onChange={(event) => setLeftWristSerial(event.target.value)} /></Field>{mode === 'dual' && <Field label="Right D405 Serial"><input list="record-camera-serials" value={rightWristSerial} disabled={!rightCameraEnabled} onChange={(event) => setRightWristSerial(event.target.value)} /></Field>}<datalist id="record-camera-serials">{(devices.data?.cameras ?? []).map((item) => <option key={item.serial} value={item.serial} />)}</datalist>
        <div className="form-grid"><Field label="Camera Width"><input type="number" min={1} value={cameraWidth} onChange={(event) => setCameraWidth(Number(event.target.value))} /></Field><Field label="Camera Height"><input type="number" min={1} value={cameraHeight} onChange={(event) => setCameraHeight(Number(event.target.value))} /></Field><Field label="FPS"><input type="number" min={1} max={60} value={fps} onChange={(event) => setFps(Number(event.target.value))} /></Field></div>
        <Field label="Max joint delta"><input type="number" min={0.001} max={0.5} step={0.005} value={delta} onChange={(event) => setDelta(Number(event.target.value))} /></Field><Field label="EMA alpha"><input type="number" min={0} max={1} step={0.05} value={ema} onChange={(event) => setEma(Number(event.target.value))} /></Field>
        <details><summary>Advanced Settings</summary><div className="switch-list"><label><input aria-label="Gripper start hold" type="checkbox" checked={gripperHold} onChange={(event) => setGripperHold(event.target.checked)} />Gripper start hold（默认关闭）</label><label><input type="checkbox" checked={returnHome} onChange={(event) => setReturnHome(event.target.checked)} />退出时返回 Home</label><label><input type="checkbox" checked={openGrippers} disabled={mode === 'single'} onChange={(event) => setOpenGrippers(event.target.checked)} />退出时张开夹爪</label><label><input type="checkbox" checked={displayData} onChange={(event) => setDisplayData(event.target.checked)} />Rerun display_data</label><label><input aria-label="Display compressed images" type="checkbox" checked={displayCompressed} onChange={(event) => setDisplayCompressed(event.target.checked)} />Display compressed images</label><label><input type="checkbox" checked={video} onChange={(event) => setVideo(event.target.checked)} />保存视频</label><label><input aria-label="Play sounds" type="checkbox" checked={playSounds} onChange={(event) => setPlaySounds(event.target.checked)} />语音提示</label><label><input aria-label="Streaming Encoding" type="checkbox" checked={streamingEncoding} onChange={(event) => setStreamingEncoding(event.target.checked)} />Streaming Encoding</label></div><div className="notice">关闭 Gripper start hold 时，录制使用 Leader 映射后的绝对夹爪目标；开始前确认 Leader 与 Follower 夹爪姿态一致。</div><div className="form-grid"><Field label="Writer Processes"><input type="number" min={0} max={32} value={writerProcesses} onChange={(event) => setWriterProcesses(Number(event.target.value))} /></Field><Field label="Writer Threads / Camera"><input type="number" min={1} max={64} value={writerThreads} onChange={(event) => setWriterThreads(Number(event.target.value))} /></Field><Field label="Video Batch Size"><input type="number" min={1} max={1000} value={videoBatchSize} onChange={(event) => setVideoBatchSize(Number(event.target.value))} /></Field><Field label="Encoder Queue Size"><input type="number" min={1} max={10000} value={encoderQueueSize} onChange={(event) => setEncoderQueueSize(Number(event.target.value))} /></Field><Field label="Encoder Threads" hint="留空为自动"><input type="number" min={1} max={128} value={encoderThreads} onChange={(event) => setEncoderThreads(event.target.value === '' ? '' : Number(event.target.value))} /></Field><Field label="Encoder Codec"><select value={encoderCodec} onChange={(event) => setEncoderCodec(event.target.value)}><option value="libsvtav1">libsvtav1</option><option value="auto">auto</option><option value="h264">h264</option><option value="hevc">hevc</option><option value="h264_nvenc">h264_nvenc</option><option value="hevc_nvenc">hevc_nvenc</option></select></Field><Field label="Encoder CRF"><input type="number" min={0} max={100} value={encoderCrf} onChange={(event) => setEncoderCrf(Number(event.target.value))} /></Field><Field label="Encoder Preset"><input type="number" min={0} max={63} value={encoderPreset} onChange={(event) => setEncoderPreset(Number(event.target.value))} /></Field><Field label="Encoder GOP"><input type="number" min={1} max={600} value={encoderGop} onChange={(event) => setEncoderGop(Number(event.target.value))} /></Field><Field label="Fast Decode"><input type="number" min={0} max={2} value={encoderFastDecode} onChange={(event) => setEncoderFastDecode(Number(event.target.value))} /></Field></div><p className="muted">默认 0 个写图进程、每相机 4 线程、libsvtav1 CRF 30。只有录制循环持续低于目标 FPS 时再调整。</p></details>
        <label className="toggle-line"><input type="checkbox" checked={resume} onChange={(event) => { setResume(event.target.checked); compatibility.reset(); setResumeExistingEpisodes(0); setResumeCompatibilityChecked(false); setTargetEpisodes(episodes) }} /><span>Resume 现有数据集（启动前执行完整契约检查）</span></label><Button variant="secondary" onClick={() => compatibility.mutate()} disabled={compatibility.isPending}>检查 Dataset Compatibility</Button>{compatibility.data && <><div className={compatibility.data.compatible ? 'notice' : 'notice notice-error'}><b>{compatibility.data.compatible ? 'COMPATIBLE' : 'INCOMPATIBLE'}</b> Existing Episodes: {compatibility.data.existing_episodes}<br />{Object.entries(compatibility.data.checks).map(([key, value]) => `${key}: ${value ? '✓' : '✗'}`).join(' · ')}{compatibility.data.message && <><br />{compatibility.data.message}</>}{compatibility.data.action && <><br />需要执行：{compatibility.data.action}</>}</div>{resume && <div className="form-grid"><Field label="已有 Episode"><input value={existingEpisodes} readOnly /></Field><Field label="目标总 Episode"><input aria-label="目标总 Episode" type="number" min={existingEpisodes + 1} max={10000} value={targetEpisodes} onChange={(event) => setTargetEpisodes(Number(event.target.value))} /></Field><Field label="本次自动新增"><input value={addEpisodes} readOnly /></Field></div>}</>}<label className="safety-check"><input aria-label="确认录制安全检查" type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><ShieldCheck /><span><b>确认录制安全检查</b>相机、CAN、配对与物理急停已确认。</span></label><ErrorNotice error={(compatibility.error ?? guardedStart.error ?? command.error ?? normalStop.error) as Error | null} /><Button disabled={!confirmed || !compatibility.data?.compatible || addEpisodes < 1 || guardedStart.isPending || taskIsActive} onClick={() => guardedStart.run(requestBody())}>{taskIsRecording && !taskIsActive ? '重新开始录制任务' : '开始录制任务'}</Button></GlassCard>
    </div>
    <PreflightDialog report={guardedStart.report} onClose={guardedStart.closeReport} onContinueSimulation={guardedStart.continueSimulation} />
  </div>
}
