import * as Dialog from '@radix-ui/react-dialog'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Check, CircleAlert, Cpu, RefreshCw, Usb, X } from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import { Button, ErrorNotice, StatusDot } from './ui'

interface DeviceCenterProps {
  open: boolean
  onOpenChange: Dispatch<SetStateAction<boolean>>
}

export function DeviceCenter({ open, onOpenChange }: DeviceCenterProps) {
  const client = useQueryClient()
  const activeTaskId = usePlatformStore((state) => state.activeTaskId)
  const inventory = useQuery({ queryKey: ['devices'], queryFn: api.devices, enabled: open, refetchInterval: open ? 4000 : false })
  const initialize = useMutation({
    mutationFn: api.initializeCan,
    onSuccess: async () => { await client.invalidateQueries({ queryKey: ['devices'] }); await client.invalidateQueries({ queryKey: ['health'] }) },
  })
  const data = inventory.data
  const readyCan = (data?.can ?? []).filter((item) => item.state === 'healthy' && item.bitrate === 1_000_000)
  const canByName = (name: string) => readyCan.find((item) => item.name === name)
  const preparation = [
    { label: '设备识别', ready: Boolean(data && ((data.usb_can?.length ?? 0) || data.mock)) },
    { label: 'SocketCAN', ready: readyCan.length >= 2 },
    { label: 'Leader', ready: (data?.leaders?.length ?? 0) >= 2 },
    { label: 'RGB 相机', ready: (data?.cameras?.length ?? 0) >= 3 },
  ]
  return <Dialog.Root open={open} onOpenChange={onOpenChange}>
    <Dialog.Portal><Dialog.Overlay className="drawer-overlay" /><Dialog.Content className="device-drawer">
      <header><div><Dialog.Title>设备准备中心</Dialog.Title><Dialog.Description>识别 → 初始化 CAN → 确认 Leader/相机 → 校准与配对</Dialog.Description></div><Dialog.Close aria-label="关闭设备中心"><X /></Dialog.Close></header>
      <div className="device-progress">{preparation.map((step, index) => <div className={step.ready ? 'ready' : ''} key={step.label}><span>{step.ready ? <Check /> : index + 1}</span><b>{step.label}</b></div>)}</div>
      <div className="device-toolbar"><div><strong>{data?.mock ? 'Mock 设备清单' : `${readyCan.length} / 2 CAN Ready`}</strong><p>初始化需要系统 Polkit 授权；Web 不保存密码，也不开放任意命令。</p></div><Button variant="secondary" onClick={() => void inventory.refetch()} disabled={inventory.isFetching}><RefreshCw size={15} />重新识别</Button></div>
      <ErrorNotice error={(inventory.error ?? initialize.error) as Error | null} />
      <section><h3><Cpu />USB-CAN 与 SocketCAN</h3><div className="device-list">{(data?.usb_can ?? []).map((adapter) => <div key={adapter.usb_path}><StatusDot state="healthy" label="Supported" /><strong>{adapter.product}</strong><code>{adapter.serial}</code><small>USB {adapter.usb_path} · {adapter.vendor_id}:{adapter.product_id}</small></div>)}{!data?.mock && !(data?.usb_can?.length ?? 0) && <div className="device-empty"><CircleAlert />未识别到 a8fa:8598 USB-CAN；检查 USB 连接后刷新。</div>}{(['can0', 'can1'] as const).map((name) => { const item = canByName(name); return <div key={name}><StatusDot state={item ? 'healthy' : 'offline'} label={item ? 'Ready' : 'Not initialized'} /><strong>{item ? `${name} · 1 Mbps` : name}</strong><small>{item ? 'UP · txqueuelen 1000' : '需要初始化并进行系统授权'}</small>{!data?.mock && !item && <Button disabled={Boolean(activeTaskId) || initialize.isPending} onClick={() => initialize.mutate(name)}>初始化 {name}</Button>}</div> })}</div></section>
      <section><h3><Usb />Leader</h3><div className="device-list compact">{(data?.leaders ?? []).map((leader) => <div key={leader.port}><StatusDot state="healthy" label={leader.state} /><strong>{leader.port}</strong><small>端口存在；7 电机握手在校准/任务启动时验证</small></div>)}{!(data?.leaders?.length ?? 0) && <div className="device-empty">未发现 `/dev/ttyACM*` Leader。</div>}</div></section>
      <section><h3><Camera />RealSense RGB</h3><div className="device-list compact">{(data?.cameras ?? []).map((camera) => <div key={camera.serial}><StatusDot state="healthy" label={camera.state} /><strong>{camera.name}</strong><code>{camera.serial}</code></div>)}{!(data?.cameras?.length ?? 0) && <div className="device-empty">未发现 RealSense；检查 USB 3.x 连接和供电。</div>}</div></section>
      <div className="notice"><b>下一步</b>设备准备后进入“机械臂校准”，分别完成左右 Leader 校准与 Leader/Follower Pairing。Follower Flash 零位维护仍不放入普通 Web 流程。</div>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>
}
