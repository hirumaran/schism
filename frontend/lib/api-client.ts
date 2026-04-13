'use client'

import type { Provider, Settings } from './types'

const AUTH_TOKEN_KEY = 'schism_auth_token'
const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL?.trim() || '/api'
export const DEFAULT_OLLAMA_CLOUD_BASE_URL = 'https://ollama.com'

export const PROVIDER_LABELS: Record<Provider, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  ollama: 'Ollama',
  mock: 'Mock',
}

export interface ResolvedProviderConfig {
  provider: Provider
  apiKey: string
  model: string
  baseUrl: string
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public override message: string,
    public detail?: string
  ) {
    super(message)
  }
}

function trimTrailingSlash(value: string): string {
  return value.endsWith('/') ? value.slice(0, -1) : value
}

export function getApiBaseUrl(): string {
  if (!RAW_API_BASE) return ''
  return trimTrailingSlash(RAW_API_BASE)
}

function getStoredAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  const localToken = window.localStorage.getItem(AUTH_TOKEN_KEY)
  if (localToken) return localToken

  const cookieToken = document.cookie
    .split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${AUTH_TOKEN_KEY}=`))

  if (!cookieToken) return null
  return decodeURIComponent(cookieToken.split('=').slice(1).join('='))
}

function clearStoredAuthToken(): void {
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(AUTH_TOKEN_KEY)
  document.cookie = `${AUTH_TOKEN_KEY}=; Max-Age=0; path=/`
}

function notifyAuthExpired(): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent('schism:auth-expired'))
}

export function resolveProviderConfig(
  settings: Settings,
  provider: Provider = settings.primaryProvider
): ResolvedProviderConfig {
  switch (provider) {
    case 'anthropic':
      return {
        provider,
        apiKey: settings.anthropicApiKey.trim(),
        model: settings.anthropicModel.trim(),
        baseUrl: '',
      }
    case 'openai':
      return {
        provider,
        apiKey: settings.openaiApiKey.trim(),
        model: settings.openaiModel.trim(),
        baseUrl: '',
      }
    case 'ollama':
      return settings.ollamaMode === 'cloud'
        ? {
            provider,
            apiKey: settings.ollamaCloudApiKey.trim(),
            model: settings.ollamaCloudModel.trim(),
            baseUrl: DEFAULT_OLLAMA_CLOUD_BASE_URL,
          }
        : {
            provider,
            apiKey: '',
            model: settings.ollamaLocalModel.trim(),
            baseUrl: settings.ollamaLocalBaseUrl.trim(),
          }
    case 'mock':
      return {
        provider,
        apiKey: '',
        model: '',
        baseUrl: '',
      }
  }
}

export function isProviderConfigured(settings: Settings, provider: Provider): boolean {
  const resolved = resolveProviderConfig(settings, provider)
  if (provider === 'mock') return true
  if (provider === 'ollama') {
    return Boolean(resolved.baseUrl || resolved.apiKey)
  }
  return Boolean(resolved.apiKey)
}

export function providerHeaders(
  settings?: Settings,
  options: { provider?: Provider; includeSecondary?: boolean } = {}
): HeadersInit {
  if (!settings) return {}
  const primary = resolveProviderConfig(settings, options.provider ?? settings.primaryProvider)
  const includeSecondary =
    options.includeSecondary !== false &&
    !options.provider &&
    settings.secondaryProvider !== null &&
    settings.secondaryProvider !== settings.primaryProvider &&
    isProviderConfigured(settings, settings.secondaryProvider)

  const headers: HeadersInit = {
    'X-Provider': primary.provider,
    'X-Embedding-Provider': settings.embeddingProvider,
  }

  if (primary.model) {
    headers['X-Model'] = primary.model
  }

  if (primary.baseUrl) {
    headers['X-Base-Url'] = primary.baseUrl
  }

  if (primary.apiKey) {
    headers['X-Api-Key'] = primary.apiKey
  }

  if (includeSecondary && settings.secondaryProvider) {
    const secondary = resolveProviderConfig(settings, settings.secondaryProvider)
    headers['X-Secondary-Provider'] = secondary.provider
    if (secondary.model) {
      headers['X-Secondary-Model'] = secondary.model
    }
    if (secondary.baseUrl) {
      headers['X-Secondary-Base-Url'] = secondary.baseUrl
    }
    if (secondary.apiKey) {
      headers['X-Secondary-Api-Key'] = secondary.apiKey
    }
  }

  return headers
}

function buildUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path
  }
  const base = getApiBaseUrl()
  if (!base) return path
  if (path.startsWith('/')) return `${base}${path}`
  return `${base}/${path}`
}

async function parseError(res: Response): Promise<ApiError> {
  const body = await res
    .json()
    .catch(() => null) as
    | { detail?: string; message?: string; error?: string }
    | null

  const detail = body?.detail || body?.message || body?.error
  return new ApiError(res.status, detail || `HTTP ${res.status}`, detail)
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & {
    settings?: Settings
    expectBlob?: boolean
  } = {}
): Promise<T> {
  const headers = new Headers(options.headers)
  const authToken = getStoredAuthToken()

  if (authToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }

  console.log('API Request:', path, {
    method: options.method,
    hasBody: !!options.body,
    bodyType: options.body?.constructor.name,
    headers: Object.fromEntries(headers.entries())
  })

  // If the body is FormData, we must NOT set the Content-Type header.
  // The browser will automatically set it to multipart/form-data with the correct boundary.
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
  })

  if (response.status === 401 && authToken) {
    clearStoredAuthToken()
    notifyAuthExpired()
  }

  if (!response.ok) {
    throw await parseError(response)
  }

  if (options.expectBlob) {
    return response.blob() as Promise<T>
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
