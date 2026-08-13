import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { websocketUrl } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import type { RealtimeEvent } from '../types'

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
        if (event.task_id) void queryClient.invalidateQueries({ queryKey: ['task', event.task_id] })
        if (event.type === 'log' && event.task_id) void queryClient.invalidateQueries({ queryKey: ['logs', event.task_id] })
      }
      socket.onclose = () => {
        setConnection('disconnected')
        if (!stopped) timer = window.setTimeout(connect, 1000)
      }
    }
    connect()
    return () => {
      stopped = true
      if (timer) window.clearTimeout(timer)
      socket?.close()
    }
  }, [acceptEvent, disabled, queryClient, setConnection])
}
