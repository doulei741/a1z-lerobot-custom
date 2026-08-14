import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { websocketUrl } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import type { RealtimeEvent } from '../types'

const TASK_STATE_EVENTS = new Set(['task', 'ready', 'health', 'fault', 'record_phase', 'calibration'])

export function shouldInvalidateTask(eventType: string) {
  return TASK_STATE_EVENTS.has(eventType)
}

export function useRealtime(disabled = false) {
  const queryClient = useQueryClient()
  const acceptEvent = usePlatformStore((state) => state.acceptEvent)
  const setConnection = usePlatformStore((state) => state.setWebsocketState)

  useEffect(() => {
    if (disabled) return
    let socket: WebSocket | null = null
    let timer: number | undefined
    let stopped = false
    const connect = () => {
      setConnection('connecting')
      socket = new WebSocket(websocketUrl(usePlatformStore.getState().lastSeq))
      socket.onopen = () => setConnection('connected')
      socket.onmessage = (message) => {
        const event = JSON.parse(message.data as string) as RealtimeEvent
        acceptEvent(event)
        if (event.task_id && shouldInvalidateTask(event.type)) void queryClient.invalidateQueries({ queryKey: ['task', event.task_id] })
        if (event.type === 'log' && event.task_id) void queryClient.invalidateQueries({ queryKey: ['logs', event.task_id] })
      }
      socket.onclose = () => {
        setConnection('disconnected')
        if (!stopped) timer = window.setTimeout(connect, 1000)
      }
    }
    // Defer the first connection by one task. React StrictMode intentionally
    // mounts, cleans up, and mounts effects again in development; deferring
    // lets the probe cleanup cancel its socket before it reaches the backend.
    timer = window.setTimeout(connect, 0)
    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
      socket?.close()
    }
  }, [acceptEvent, disabled, queryClient, setConnection])
}
