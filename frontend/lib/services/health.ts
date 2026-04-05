'use client'

import { apiRequest, ApiError, providerHeaders } from '@/lib/api-client'
import type { HealthResponse, Settings } from '@/lib/types'

export async function healthCheck(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health')
}

export async function validateKey(settings: Settings): Promise<boolean> {
  try {
    await apiRequest<HealthResponse>('/health', {
      headers: providerHeaders(settings),
    })
    return true
  } catch (error) {
    if (error instanceof ApiError) {
      return false
    }
    throw error
  }
}

export async function testOllamaConnection(baseUrl: string): Promise<{ models: string[] }> {
  const normalized = baseUrl.replace(/\/$/, '')
  const response = await fetch(`${normalized}/api/tags`)
  if (!response.ok) {
    throw new ApiError(response.status, 'Cannot connect to Ollama')
  }
  const data = await response.json()
  return { models: data.models?.map((model: { name: string }) => model.name) ?? [] }
}
