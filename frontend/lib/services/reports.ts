'use client'

import { apiRequest, providerHeaders } from '@/lib/api-client'
import type { Report, Settings } from '@/lib/types'

export async function getReport(reportId: string, settings: Settings): Promise<Report> {
  return apiRequest<Report>(`/reports/${reportId}`, {
    headers: providerHeaders(settings),
  })
}

export async function exportReport(
  reportId: string,
  format: 'json' | 'csv',
  settings: Settings
): Promise<Blob> {
  return apiRequest<Blob>(`/reports/${reportId}/export?format=${format}`, {
    headers: providerHeaders(settings),
    expectBlob: true,
  })
}
