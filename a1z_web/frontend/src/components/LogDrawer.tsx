import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { Clipboard, Download, Pause, Play, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import { Button } from './ui'

export function LogDrawer() {
  const open = usePlatformStore((state) => state.logDrawerOpen)
  const setOpen = usePlatformStore((state) => state.setLogDrawer)
  const taskId = usePlatformStore((state) => state.activeTaskId)
  const [filter, setFilter] = useState('ALL')
  const [paused, setPaused] = useState(false)
  const [hiddenBefore, setHiddenBefore] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)
  const logs = useQuery({ queryKey: ['logs', taskId], queryFn: () => api.logs(taskId!), enabled: Boolean(taskId) && open && !paused, refetchInterval: 1000 })
  const items = useMemo(() => (logs.data?.items ?? []).filter((entry) => entry.seq > hiddenBefore && (filter === 'ALL' || entry.level === filter)), [filter, hiddenBefore, logs.data])
  const text = items.map((entry) => `${entry.timestamp} ${entry.level} ${entry.source} ${entry.message}`).join('\n')
  useEffect(() => {
    if (!paused && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [items, paused])
  const download = () => {
    const blob = new Blob([text], { type: 'text/plain' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${taskId ?? 'a1z'}-logs.txt`
    link.click()
    URL.revokeObjectURL(link.href)
  }
  return <Dialog.Root open={open} onOpenChange={setOpen}>
    <Dialog.Portal><Dialog.Overlay className="drawer-overlay" /><Dialog.Content className="log-drawer">
      <header><div><Dialog.Title>任务日志</Dialog.Title><Dialog.Description>{taskId ?? '尚无活动任务'}</Dialog.Description></div><Dialog.Close aria-label="关闭日志"><X /></Dialog.Close></header>
      <div className="log-toolbar">
        <div className="filter-row">{['ALL', 'INFO', 'WARN', 'ERROR'].map((level) => <button className={filter === level ? 'active' : ''} onClick={() => setFilter(level)} key={level}>{level}</button>)}</div>
        <Button variant="secondary" onClick={() => setPaused(!paused)}>{paused ? <Play size={15} /> : <Pause size={15} />}{paused ? '继续' : '暂停滚动'}</Button>
        <Button variant="secondary" onClick={() => void navigator.clipboard.writeText(text)}><Clipboard size={15} />复制</Button>
        <Button variant="secondary" onClick={() => setHiddenBefore(logs.data?.next_seq ?? 0)}><Trash2 size={15} />清空显示</Button>
        <Button variant="secondary" onClick={download}><Download size={15} />下载</Button>
      </div>
      <div className="log-list" ref={listRef}>{items.length ? items.map((entry) => <div className={`log-line log-${entry.level.toLowerCase()}`} key={entry.seq}><time>{new Date(entry.timestamp).toLocaleTimeString()}</time><b>{entry.level}</b><span>{entry.source}</span><p>{entry.message}</p></div>) : <div className="empty">暂无日志</div>}</div>
    </Dialog.Content></Dialog.Portal>
  </Dialog.Root>
}
