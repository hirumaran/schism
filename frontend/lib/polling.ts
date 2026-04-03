'use client'

import { useQuery } from '@tanstack/react-query'
import * as api from './api'
import type { Settings } from './types'

export function useJobPolling(jobId: string, settings: Settings) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.getJob(jobId, settings),
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000
      const terminal = ['done', 'failed', 'cancelled']
      if (terminal.includes(data.status)) return false
      return 2000
    },
    staleTime: 0,
  })
}

export function useJobResults(
  jobId: string,
  settings: Settings,
  filters: { type?: string; mode?: string; limit?: number; offset?: number }
) {
  return useQuery({
    queryKey: ['results', jobId, filters],
    queryFn: () => api.getJobResults(jobId, filters, settings),
    enabled: true,
    staleTime: 30000,
  })
}

export function useLiveClaimsPreview(
  jobId: string,
  settings: Settings,
  isActive: boolean
) {
  return useQuery({
    queryKey: ['preview', jobId],
    queryFn: () => api.getJobResults(jobId, { limit: 3 }, settings),
    refetchInterval: isActive ? 4000 : false,
    enabled: isActive,
  })
}

export function useReport(reportId: string, settings: Settings) {
  return useQuery({
    queryKey: ['report', reportId],
    queryFn: () => api.getReport(reportId, settings),
    staleTime: 60000,
  })
}
