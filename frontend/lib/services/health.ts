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
  const trimmedKey = apiKey?.trim()

  try {
    return await apiRequest<{ models: string[] }>('/ollama/tags', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        base_url: normalized,
        api_key: trimmedKey || undefined,
      }),
    })
  } catch (error) {
    if (error instanceof ApiError) {
      if (trimmedKey && (error.status === 401 || error.status === 403)) {
        throw new ApiError(error.status, 'Invalid Ollama API key')
      }
      throw new ApiError(
        error.status,
        trimmedKey ? 'Cannot reach Ollama Cloud' : 'Cannot connect to Ollama'
      )
    }

    throw new ApiError(0, trimmedKey ? 'Cannot reach Ollama Cloud' : 'Cannot connect to Ollama')
  }
}
