import { useMutation } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { ApiError } from '../services/api'
import type { PreflightReport, TaskInfo } from '../types'

export function usePreflightStart(
  preflight: (request: Record<string, unknown>) => Promise<PreflightReport>,
  start: (request: Record<string, unknown>) => Promise<TaskInfo>,
  onStarted: (task: TaskInfo) => void,
) {
  const [report, setReport] = useState<PreflightReport | null>(null)
  const pendingRequest = useRef<Record<string, unknown> | null>(null)
  const startMutation = useMutation({
    mutationFn: start,
    onSuccess: onStarted,
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'hardware_preflight_failed') {
        setReport(error.details as unknown as PreflightReport)
      }
    },
  })
  const preflightMutation = useMutation({
    mutationFn: preflight,
    onSuccess: (result, request) => {
      if (!result.ready || result.simulation) {
        setReport(result)
        return
      }
      startMutation.mutate(request)
    },
  })

  const run = (request: Record<string, unknown>) => {
    pendingRequest.current = request
    setReport(null)
    preflightMutation.mutate(request)
  }
  const continueSimulation = () => {
    const request = pendingRequest.current
    setReport(null)
    if (request) startMutation.mutate(request)
  }

  return {
    run,
    report,
    closeReport: () => setReport(null),
    continueSimulation,
    isPending: preflightMutation.isPending || startMutation.isPending,
    error: preflightMutation.error ?? startMutation.error,
  }
}
