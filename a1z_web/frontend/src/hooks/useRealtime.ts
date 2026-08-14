import { useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { websocketUrl } from '../services/api'
import { usePlatformStore } from '../stores/platform'
import type { RealtimeEvent } from '../types'

const TASK_STATE_EVENTS = new Set(['task', 'ready', 'health', 'fault', 'record_phase', 'calibration'])
type EventSubscriber = (event: RealtimeEvent) => void

const subscribers = new Set<EventSubscriber>()
let sharedSocket: WebSocket | null = null
let connectTimer: number | undefined
let reconnectTimer: number | undefined

function clearTimer(timer: number | undefined) {
  if (timer !== undefined) window.clearTimeout(timer)
}

function connectSharedSocket() {
  if (subscribers.size === 0 || sharedSocket || connectTimer !== undefined) return
  usePlatformStore.getState().setWebsocketState('connecting')
  connectTimer = window.setTimeout(() => {
    connectTimer = undefined
    if (subscribers.size === 0 || sharedSocket) return

    const socket = new WebSocket(websocketUrl(usePlatformStore.getState().lastSeq))
    sharedSocket = socket
    socket.onopen = () => usePlatformStore.getState().setWebsocketState('connected')
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data as string) as RealtimeEvent
      usePlatformStore.getState().acceptEvent(event)
      subscribers.forEach((subscriber) => subscriber(event))
    }
    socket.onclose = () => {
      if (sharedSocket !== socket) return
      sharedSocket = null
      usePlatformStore.getState().setWebsocketState('disconnected')
      if (subscribers.size > 0) {
        reconnectTimer = window.setTimeout(() => {
          reconnectTimer = undefined
          connectSharedSocket()
        }, 1000)
      }
    }
  }, 0)
}

function subscribeToRealtime(subscriber: EventSubscriber) {
  subscribers.add(subscriber)
  clearTimer(reconnectTimer)
  reconnectTimer = undefined
  connectSharedSocket()

  return () => {
    subscribers.delete(subscriber)
    if (subscribers.size > 0) return
    clearTimer(connectTimer)
    clearTimer(reconnectTimer)
    connectTimer = undefined
    reconnectTimer = undefined
    const socket = sharedSocket
    sharedSocket = null
    if (socket) {
      socket.onclose = null
      socket.close()
    }
    usePlatformStore.getState().setWebsocketState('disconnected')
  }
}

export function shouldInvalidateTask(eventType: string) {
  return TASK_STATE_EVENTS.has(eventType)
}

export function useRealtime(disabled = false) {
  const queryClient = useQueryClient()

  useEffect(() => {
    if (disabled) return
    return subscribeToRealtime((event) => {
      if (event.task_id && shouldInvalidateTask(event.type)) void queryClient.invalidateQueries({ queryKey: ['task', event.task_id] })
      if (event.type === 'log' && event.task_id) void queryClient.invalidateQueries({ queryKey: ['logs', event.task_id] })
    })
  }, [disabled, queryClient])
}
