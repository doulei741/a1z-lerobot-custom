import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { RealtimeEvent } from '../types'

interface PlatformState {
  activeTaskId: string | null
  activeTaskType: string | null
  taskPhase: string | null
  logDrawerOpen: boolean
  websocketState: 'connecting' | 'connected' | 'disconnected'
  lastSeq: number
  setActiveTask: (id: string | null, type?: string | null) => void
  setPhase: (phase: string | null) => void
  setLogDrawer: (open: boolean) => void
  setWebsocketState: (state: PlatformState['websocketState']) => void
  acceptEvent: (event: RealtimeEvent) => void
}

export const usePlatformStore = create<PlatformState>()(persist((set) => ({
  activeTaskId: null,
  activeTaskType: null,
  taskPhase: null,
  logDrawerOpen: false,
  websocketState: 'disconnected',
  lastSeq: 0,
  setActiveTask: (activeTaskId, activeTaskType = null) => set({ activeTaskId, activeTaskType }),
  setPhase: (taskPhase) => set({ taskPhase }),
  setLogDrawer: (logDrawerOpen) => set({ logDrawerOpen }),
  setWebsocketState: (websocketState) => set({ websocketState }),
  acceptEvent: (event) => set((state) => ({
    lastSeq: Math.max(state.lastSeq, event.seq),
    taskPhase: event.task_id === state.activeTaskId && typeof event.data.phase === 'string'
      ? event.data.phase
      : state.taskPhase,
  })),
}), {
  name: 'a1z-web-active-task',
  partialize: (state) => ({ activeTaskId: state.activeTaskId, activeTaskType: state.activeTaskType, lastSeq: state.lastSeq }),
}))
