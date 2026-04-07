'use client'

import { apiRequest, providerHeaders } from '@/lib/api-client'
import type { AnalyzeAcceptedResponse, SearchResponse, Settings } from '@/lib/types'

export async function analyzeQuery(
  params: { query: string; max_results: number; sources: string[] },
  settings: Settings
): Promise<AnalyzeAcceptedResponse> {
  return apiRequest<AnalyzeAcceptedResponse>('/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...providerHeaders(settings),
    },
    body: JSON.stringify(params),
  })
}

export async function analyzePaper(
  params: {
    file?: File
    text?: string
    title?: string
    max_results: number
    sources: string[]
  },
  settings: Settings
): Promise<AnalyzeAcceptedResponse> {
  if (params.file) {
    console.log('Sending file:', params.file.name, params.file.size)
    const formData = new FormData()
    formData.append('file', params.file)
    formData.append('max_results', params.max_results.toString())
    formData.append('sources', params.sources.join(','))
    formData.append('title', params.title || params.file.name)

    return apiRequest<AnalyzeAcceptedResponse>('/analyze/paper', {
      method: 'POST',
      headers: {
        ...providerHeaders(settings),
      },
      body: formData,
    })
  }

  return apiRequest<AnalyzeAcceptedResponse>('/analyze/paper', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...providerHeaders(settings),
    },
    body: JSON.stringify({
      text: params.text,
      title: params.title,
      max_results: params.max_results,
      sources: params.sources,
    }),
  })
}

export async function searchPapers(
  params: {
    query: string
    max_results: number
    sources: string[]
    year_min?: number
    year_max?: number
    min_citations?: number
  }
): Promise<SearchResponse> {
  const searchParams = new URLSearchParams()
  if (params.year_min !== undefined) searchParams.set('year_min', params.year_min.toString())
  if (params.year_max !== undefined) searchParams.set('year_max', params.year_max.toString())
  if (params.min_citations !== undefined) searchParams.set('min_citations', params.min_citations.toString())
  if (params.sources.length > 0) searchParams.set('sources', params.sources.join(','))

  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : ''
  return apiRequest<SearchResponse>(`/search${suffix}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: params.query,
      max_results: params.max_results,
      sources: params.sources,
    }),
  })
}
