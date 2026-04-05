'use client'

import { apiRequest, providerHeaders } from '@/lib/api-client'
import type { AnalysisJob, JobResults, JobStats, Settings } from '@/lib/types'

export async function getJob(jobId: string, settings: Settings): Promise<AnalysisJob> {
  return apiRequest<AnalysisJob>(`/jobs/${jobId}`, {
    headers: providerHeaders(settings),
  })
}

export async function getJobStats(jobId: string, settings: Settings): Promise<JobStats> {
  return apiRequest<JobStats>(`/jobs/${jobId}/stats`, {
    headers: providerHeaders(settings),
  })
}

export async function getJobResults(
  jobId: string,
  params: { type?: string; mode?: string; limit?: number; offset?: number },
  settings: Settings
): Promise<JobResults> {
  const searchParams = new URLSearchParams()
  if (params.type) searchParams.set('type', params.type)
  if (params.mode) searchParams.set('mode', params.mode)
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString())
  if (params.offset !== undefined) searchParams.set('offset', params.offset.toString())
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : ''

  return apiRequest<JobResults>(`/jobs/${jobId}/results${suffix}`, {
    headers: providerHeaders(settings),
  })
}

export async function cancelJob(jobId: string, settings: Settings): Promise<void> {
  await apiRequest<void>(`/jobs/${jobId}`, {
    method: 'DELETE',
    headers: providerHeaders(settings),
  })
}
