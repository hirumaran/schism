'use client'

import { apiRequest, ApiError, providerHeaders } from '@/lib/api-client'
import type { HealthResponse, Provider, Settings } from '@/lib/types'

export async function healthCheck(): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health')
}

export async function validateKey(settings: Settings, provider?: Provider): Promise<boolean> {
  try {
    await apiRequest<HealthResponse>('/health', {
      headers: providerHeaders(settings, { provider, includeSecondary: false }),
    })
    return true
  } catch (error) {
    if (error instanceof ApiError) {
      return false
    }
    throw error
  }
}

export async function testOllamaConnection(baseUrl: string, apiKey?: string): Promise<{ models: string[] }> {
  const normalized = baseUrl.replace(/\/$/, '')
  const response = await fetch(`${normalized}/api/tags`, {
    headers: apiKey ? { Authorization: `Bearer ${apiKey}` } : undefined,
  })

  if (!response.ok) {
    if (apiKey && (response.status === 401 || response.status === 403)) {
      throw new ApiError(response.status, 'Invalid Ollama API key')
    }
    throw new ApiError(
      response.status,
      apiKey ? 'Cannot reach Ollama Cloud' : 'Cannot connect to Ollama'
    )
  }

  const data = await response.json()
  return { models: data.models?.map((model: { name: string }) => model.name) ?? [] }
}
