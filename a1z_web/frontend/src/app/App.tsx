import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { MemoryRouter, Navigate, Route, Routes, BrowserRouter } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { useRealtime } from '../hooks/useRealtime'
import { Calibration } from '../pages/Calibration'
import { Inference } from '../pages/Inference'
import { Recording } from '../pages/Recording'
import { Teleoperation } from '../pages/Teleoperation'

function RoutedApp({ disableRealtime = false }: { disableRealtime?: boolean }) {
  useRealtime(disableRealtime)
  return <AppShell><Routes><Route path="/calibration" element={<Calibration />} /><Route path="/teleoperation" element={<Teleoperation />} /><Route path="/recording" element={<Recording />} /><Route path="/inference" element={<Inference />} /><Route path="*" element={<Navigate to="/calibration" replace />} /></Routes></AppShell>
}

export function App({ initialPath, disableRealtime = false }: { initialPath?: string; disableRealtime?: boolean }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 1000 }, mutations: { retry: false } } }))
  const Router = initialPath ? MemoryRouter : BrowserRouter
  const routerProps = initialPath ? { initialEntries: [initialPath] } : {}
  return <QueryClientProvider client={client}><Router {...routerProps}><RoutedApp disableRealtime={disableRealtime} /></Router></QueryClientProvider>
}
